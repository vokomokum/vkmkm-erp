#! /usr/bin/perl -w 
# $Id: adm_view_memord.cgi,v 1.2 2010/04/13 06:19:46 jes Exp jes $

package view_member;

use strict;
use Config::General;
use Data::Dumper;
use DBI;
use CGI::FastTemplate;
use CGI::Pretty qw(:standard);
use CGI::Carp 'fatalsToBrowser';
use Unix::Syslog qw( :macros :subs );
use POSIX qw(strftime);
use MIME::Base64;
use voko;

BEGIN {
    use Exporter   ();
    our ($VERSION, @ISA, @EXPORT, @EXPORT_OK, %EXPORT_TAGS);

    $VERSION     = sprintf "%d.%03d", q$Revision: 1.2 $ =~ /(\d+)/g;

    @ISA         = qw(Exporter);
    @EXPORT      = qw(display_mem_order totals_html );
    %EXPORT_TAGS = ( );     # eg: TAG => [ qw!name1 name2! ],
    @EXPORT_OK   = ();
}
our @EXPORT_OK;
my %categories;
my %cat_descs;
my %sc_descs;

# sort by cat, subcat, desc alpha
sub pr_sort{
    my $aid = 100000 * $a->{pr_cat} + $a->{pr_sc};
    my $bid = 100000 * $b->{pr_cat} + $b->{pr_sc};
    my $cmp = ($sc_descs{$aid}->{sort_ord} <=> $sc_descs{$bid}->{sort_ord});
    return $cmp if($cmp != 0);
    return ($a->{pr_desc} cmp $b->{pr_desc});
}

sub vm_get_vars {
    my ($config, $cgi, $dbh) = @_;
    my %pr_dat;
    my $vals = $cgi->Vars;
    my %new_vals;
    my %buttons;

    $config->{showbtw} = (defined($vals) and (defined($vals->{showbtw}))); 
    $config->{showall} = (defined($vals) and (defined($vals->{showall}))); 
    $config->{showbtw} = 0 if($config->{showall});
}

# return btw on qty, ex_btw price as an integer no of eurocents
sub btw {
    my ($qty, $ex_pr, $btw) = @_;
    $btw = int(10 * $btw);
    return int(($qty * $ex_pr * $btw + 500) / 1000);
}
					      
sub get_products {
    my ($config,$cgi, $dbh) = @_;

    my $h;
    my $sth;
    # get a list of all the pr_ids for this order
    my @ml_hashes;
    my @hashes;
    $sth = prepare("SELECT * FROM mem_line WHERE ord_no = ? ".
		      "AND mem_id = ?", $dbh);
    $sth->execute($config->{ord_no}, $config->{mem_id});
    push @hashes, $h while $h = $sth->fetchrow_hashref;
    $sth->finish;

    # add the descriptions and data for shortages from join of product
    # and wholesale line
    $sth = prepare("SELECT p.pr_desc, p.pr_mem_q, p.pr_wh_q, w.whl_mem_qty, ".
		   "p.pr_wh, p.wh_prcode, p.pr_cat, p.pr_sc  " .
		   "FROM product AS p, wh_line AS w  WHERE p.pr_id = ?". 
		   "AND p.pr_id = w.pr_id AND w.ord_no = ?", $dbh); 
    foreach $h (@hashes) {
	$sth->execute($h->{pr_id}, $h->{ord_no});
	my $href = $sth->fetchrow_hashref;
	next if(not defined($href));
	# append the new data to the line items
	foreach my $k (keys %{$href}) {
	    $h->{$k} = $href->{$k};
	}
	push @ml_hashes, $h;
    }
    $sth->finish;
    # now prepare the values we may need to display
    foreach $h (@ml_hashes) {
	$h->{RowClass} = "myorder";
    	$h->{pr_desc} = $cgi->escapeHTML( $h->{pr_desc} );
	$h->{pr_desc} =~ s/BULK/<B>BULK<\/B>/;

	# some renaming
	$h->{mem_qty} = $h->{whl_mem_qty};
	$h->{order}   = $h->{meml_pickup};
	$h->{pr_mem_price} = $h->{meml_unit_price};
	# with btw price
	$h->{cost_ex_btw}  = sprintf "%0.2f",
		($h->{meml_pickup} * $h->{meml_ex_btw}) /100.0;
	$h->{cost}    = sprintf "%0.2f", ($h->{meml_pickup} * $h->{meml_ex_btw} +
					 btw($h->{meml_pickup}, $h->{meml_ex_btw},
					     $h->{meml_btw}))/100.0;
	$h->{meml_ex_btw} = sprintf "%0.2f", $h->{meml_ex_btw}/100.0;
	$h->{meml_unit_price} = sprintf "%0.2f", $h->{meml_unit_price}/100.0;
	# compute shortage
	$h->{short} = (($h->{mem_qty} % $h->{pr_wh_q}) == 0) ?
	    0 : $h->{pr_wh_q} - ($h->{mem_qty} % $h->{pr_wh_q});
    }
    my @sorted = sort pr_sort @ml_hashes;
    return \@sorted;
}

# set up display titles etc.
sub set_titles {
    my ($config, $cgi, $dbh) = @_;
    vm_get_vars($config, $cgi, $dbh);

    if($config->{showall}) {
	$config->{row}         = "adm_view_memord/noeditprrow_w_all.template";
	$config->{footer}      = "adm_view_memord/footer_w_all.template";
	$config->{footer_xfer} = "adm_view_memord/footer_xfer_w_all.template";
	$config->{footer_pymt} = "adm_view_memord/footer_pymt_w_all.template";
	$config->{col_hdr}     = "adm_view_memord/titles_w_all.template";
	$config->{sub_total}   = "adm_view_memord/item_tot_w_all.template";
	$config->{notes}       = "adm_view_memord/footer_notes_w_all.template";
    } elsif($config->{showbtw}) {
	$config->{row}         = "adm_view_memord/noeditprrow_w_btw.template";
	$config->{footer}      = "adm_view_memord/footer_w_btw.template";
	$config->{footer_xfer} = "adm_view_memord/footer_xfer_w_btw.template";
	$config->{footer_pymt} = "adm_view_memord/footer_pymt_w_btw.template";
	$config->{col_hdr}     = "adm_view_memord/titles_w_btw.template";
	$config->{sub_total}   = "adm_view_memord/item_tot_w_btw.template";
	$config->{notes}       = "adm_view_memord/footer_notes_w_btw.template";
    } else {
	$config->{row}         = "adm_view_memord/noeditprrow.template";
	$config->{footer}      = "adm_view_memord/footer.template";
	$config->{footer_xfer} = "adm_view_memord/footer_xfer.template";
	$config->{footer_pymt} = "adm_view_memord/footer_pymt.template";
	$config->{col_hdr}     = "adm_view_memord/titles.template";
	$config->{sub_total}   = "adm_view_memord/item_tot.template";
	$config->{notes}       = "adm_view_memord/footer_notes.template";
    }
    if ( $config->{status} >= 3 ) {
	if($config->{showall}) {
	    $config->{row}     = "common/mem_order_row_w_all.template";
	    $config->{col_hdr} = "common/mem_order_cols_w_all.template";
	    $config->{footer}  = "common/mem_order_footer_w_all.template";
	    $config->{footer_xfer} = "common/mem_order_footer_xfer_w_all.template";
	    $config->{footer_pymt} = "common/mem_order_footer_pymt_w_all.template";
	    $config->{sub_total}   = "common/item_tot_w_all.template";
	    $config->{notes}       = "common/footer_notes_w_all.template";
	} elsif($config->{showbtw}) {
	    $config->{row}     = "common/mem_order_row_w_btw.template";
	    $config->{col_hdr} = "common/mem_order_cols_w_btw.template";
	    $config->{footer}  = "common/mem_order_footer_w_btw.template";
	    $config->{footer_xfer} = "common/mem_order_footer_xfer_w_btw.template";
	    $config->{footer_pymt} = "common/mem_order_footer_pymt_w_btw.template";
	    $config->{sub_total}   = "common/item_tot_w_btw.template";
	$config->{notes}       = "common/footer_notes_w_btw.template";
	} else {
	    $config->{row}     = "common/mem_order_row.template";
	    $config->{col_hdr} = "common/mem_order_cols.template";
	    $config->{footer}  = "common/mem_order_footer.template";
	    $config->{footer_xfer} = "common/mem_order_footer_xfer.template";
	    $config->{footer_pymt} = "common/mem_order_footer_pymt.template";
	    $config->{sub_total}   = "common/item_tot.template";
	    $config->{notes}       = "common/footer_notes.template";
	}
    }
}

# payment column names and text
our %cols = (mo_stgeld_rxed=>{text => "Statiegeld for items in this order",
			      ord  => 1, credit => ""},
	     mo_stgeld_refunded=>{text =>"Statiegeld repaid to member",
				  ord => 2, credit => "Credit"},
	     mo_crates_rxed=>{text => "Deposit for crates with this order",
			      ord => 3, credit => ""},
	     mo_crates_refunded=>{text=>"Deposit returned for crates",
				  ord => 4, credit => "Credit"},
	     mo_membership=>{text=>"Membership",
			     ord => 5, credit => ""},
	     mo_misc_rxed=>{text=>"Miscellaneous charges (see notes)",
			    ord => 6, credit => ""},
	     mo_misc_refunded=>{text => "Miscellaneous credits (see notes)",
				ord => 7, credit => "Credit"},
	     mo_vers_groente=>{text => "Vers groente", ord =>  8, credit => ""},
	     mo_vers_kaas   =>{text => "Vers kaas, eieren en brood",    ord =>  9, credit => ""},
	     mo_vers_misc   =>{text => "Vers misc",    ord => 10, credit => ""},
);

# get the order totals
# returns a monster hashref
sub get_totals {
    my ($mem_id, $ord_no, $ml_hashes, $config, $dbh) = @_;
    my  %result = ( transfer_in  => {},
		    transfer_out => {},
		    payments     => {},
		    btws         => {},
		    notes        => "",
	);
    my ($sth, $sth_in, $sth_out);
    my ($h, $href);
    # get details (member no and qty) of all transfers
    $sth_in  = prepare("SELECT * FROM xfer WHERE to_id=? AND pr_id=? AND ord_no=?", 
		       $dbh);
    $sth_out = prepare("SELECT * FROM xfer WHERE from_id=? AND pr_id=? AND ord_no=?", 
		       $dbh);
    foreach $h (@{$ml_hashes}) {
	if($h->{meml_xfer_in} != 0) {
	    $sth_in->execute($config->{mem_id}, $h->{pr_id}, 
			     $config->{ord_no});
	    while($href = $sth_in->fetchrow_hashref) {
		if(not defined($result{transfer_in}->{$h->{pr_id}})) {
		    $result{transfer_in}->{$h->{pr_id}} = [];
		}
		push @{$result{transfer_in}->{$h->{pr_id}}}, 
			"$href->{from_id}:$href->{qty}";
	    }
	}
	next if($h->{meml_xfer_out} == 0);
	$sth_out->execute($config->{mem_id}, $h->{pr_id}, $config->{ord_no});
	while($href = $sth_out->fetchrow_hashref) {
	    if(not defined($result{transfer_out}->{$h->{pr_id}})) {
		$result{transfer_out}->{$h->{pr_id}} = [];
	    }
	    push @{$result{transfer_out}->{$h->{pr_id}}}, 
	    	"$href->{to_id}:$href->{qty}";
	}
    }
    $sth_in->finish;
    $sth_out->finish;
  
    $sth = prepare("SELECT * FROM mem_order WHERE ord_no = ? AND mem_id = ?",
		   $dbh);
    $sth->execute($config->{ord_no}, $config->{mem_id});
    $href = $sth->fetchrow_hashref;
    $sth->finish;
    my $p = $result{payments};
    # create a hash of the various payments, default to zeros if
    # no mem_order header
    if(defined($href)) {
	foreach my $key (keys %cols) { 
	    $p->{$key} = $href->{$key}; 
	}
    } else {
	foreach my $key (keys %cols) { 
	    $p->{$key} = 0;
	}
    }

    # get the ex-btw amounts and btw amounts by bands, then totals
    # 3 sets sum_ex_bte, btw-rate, btw_amdt, then sum all btw, order total
    $result{btws} = get_ord_totals($config->{mem_id}, 
				   $config->{ord_no}, $dbh);

    my $sth_notes = prepare("SELECT note FROM order_notes ".
			    "WHERE mem_id = ? AND ord_no = ?", 
			    $dbh);
    $sth_notes->execute($config->{mem_id}, $config->{ord_no});
    my $a = $sth_notes->fetchrow_arrayref;
    #dump_stuff("notes", $config->{mem_id}, $config->{ord_no}, $a);
    $result{notes} = $a->[0] if(defined($a));
    #dump_stuff("get_totals", "", "", $a);
    return \%result;
}

sub print_html {
    my ($ml_hashes, $config, $cgi, $dbh) = @_;
    
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/view_member_checkboxes.template");
    my %hdr_h =(  btwchecked  => (($config->{showbtw}) ? 
		 "CHECKED" : ""),
		 allchecked   => (($config->{showall}) ? 
		 "CHECKED" : ""),
		  BUTTONS     => "",
	);

    $tpl->strict();
    $tpl->assign(\%hdr_h);
    #$tpl->parse(BUTTONS => "prbuttons");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    my $line = 0;
    my $h;
    my $p;
    foreach $h (@{$ml_hashes}) {
	if ( ( $line %21 ) == 0 ) {
	    my $tpt = new CGI::FastTemplate($config->{templates});
	    $tpt->define( line => $config->{col_hdr} );
	    $tpt->assign( {Description => "Description", cat => '0'} );
	    $tpt->parse( MAIN => "line" );
	    $tpt->print( "MAIN" );
	    $tpt = undef;
	    ++$line;
	}
	# skip lines which didn't make it through delivery
	# and weren't transferred in
	# shortages unless we're doing everything
	next if(not $config->{showall} and $h->{meml_pickup} == 0
	   and $h->{ml_recv} == 0);

	++$line;
	my $tplr = new CGI::FastTemplate( $config->{templates} );
	my $url_temp = "common/zap_url.template";
	if ($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BG}->{bg_wh_id} and 
		$config->{BG}->{$h->{pr_id}}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{BG}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BUBBLE_CLUB}->{bc_wh_id} and 
		$config->{BUBBLE_CLUB}->{$h->{pr_id}}) {
	    $url_temp = "common/bclub_url.template";
	    $h->{wh_url} = $config->{BUBBLE_CLUB}->{$h->{pr_id}};
	} else {
	    $url_temp = "common/no_url.template";
	    $h->{URL} = "";
	}

	$tplr->define(row => $config->{row},
		     url => $url_temp);
	$tplr->assign($h);
	$tplr->parse("URL", "url");
	    
	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;

    }
	
    if ( $line == 0 ) {
	my $tpt = new CGI::FastTemplate($config->{templates});
	$tpt->define( line => $config->{col_hdr} );
	$tpt->assign( {Description => 'Description'} );
	$tpt->parse( MAIN => "line" );
	$tpt->print( "MAIN" );
	$tpt = undef;
    }

    my $tot_hash = get_totals($config->{mem_id}, $config->{ord_no}, 
			      $ml_hashes,  $config, $dbh);
    
    my @arr = @{$tot_hash->{btws}};
    my $totref = {items_w_btw  => sprintf("%.2f", ($arr[9] + $arr[10]) / 100.),
		items_ex_btw => sprintf("%.2f", $arr[9]/ 100.),
		total_btw    => sprintf("%.2f", $arr[10] / 100.)
    };
    #dump_stuff("view_mem", "tothash", "", $tot_hash);
    my $href;

    my $tplif = new CGI::FastTemplate( $config->{templates} );
    $tplif->define( footer => $config->{sub_total}); 
    $tplif->strict();
    $tplif->assign($totref);
    $tplif->parse(MAIN => "footer");
    $tplif->print();
    $tplif = undef;


    if($config->{status} >= 3) {
	$p = $tot_hash->{transfer_in};
	foreach $h (@{$ml_hashes}) {
	    next if(not defined($p->{$h->{pr_id}}));
	    my $aref = $p->{$h->{pr_id}};
	    foreach my $str (@{$aref}) {
		$href = {dir1=>"Received ", dir2=>" items of product code ", 
			 pr_id=>$h->{pr_id}, dir3=>" from order for member "};
		($href->{mem}, $href->{qty}) = split(':', $str);
    
		my $tplf = new CGI::FastTemplate( $config->{templates} );
		$tplf->define( footer => $config->{footer_xfer} );
		$tplf->strict();
		$tplf->assign($href);
		$tplf->parse(MAIN => "footer");
		$tplf->print();
		$tplf = undef;
	    }
	}
	$p = $tot_hash->{transfer_out};
	foreach $h (@{$ml_hashes}) {
	    next if(not defined($p->{$h->{pr_id}}));
	    my $aref = $p->{$h->{pr_id}};
	    foreach my $str (@{$aref}) {
		$href = {dir1=>"Transferred ", dir2=>" items of product code ", 
			 pr_id=>$h->{pr_id}, dir3=>" to order for member "};
		($href->{mem}, $href->{qty}) = split(':', $str);
		my $tplf = new CGI::FastTemplate( $config->{templates} );
		$tplf->define( footer => $config->{footer_xfer} );
		$tplf->strict();
		$tplf->assign($href);
		$tplf->parse(MAIN => "footer");
		$tplf->print();
		$tplf = undef;
	    }
	}
	foreach $h (@{$ml_hashes}) {
	    if($h->{meml_missing} != 0) {
		$href = {dir1=>"",  qty=>$h->{meml_missing}, 
			 dir2=>" item(s) of product code ", 
			 pr_id=>$h->{pr_id}, dir3=>" were missing", mem=>""};
		my $tplf = new CGI::FastTemplate( $config->{templates} );
		$tplf->define( footer => $config->{footer_xfer} );
		$tplf->strict();
		$tplf->assign($href);
		$tplf->parse(MAIN => "footer");
		$tplf->print();
		$tplf = undef;
	    }
	    if($h->{meml_damaged} != 0) {
		$href = {dir1=>"",  qty=>$h->{meml_damaged}, 
			 dir2=>" item(s) of prdcuct code ", 
			 pr_id=>$h->{pr_id}, dir3=>" were damaged or broken", mem=>""};
		my $tplf = new CGI::FastTemplate( $config->{templates} );
		$tplf->define( footer => $config->{footer_xfer} );
		$tplf->strict();
		$tplf->assign($href);
		$tplf->parse(MAIN => "footer");
		$tplf->print();
		$tplf = undef;
	    }
	}
    }

    my $total = 0;
    $p = $tot_hash->{payments};

    foreach my $key (sort {$cols{$a}->{ord} <=> $cols{$b}->{ord}} (keys %cols)) {
	
	next if(not defined($p->{$key}) or $p->{$key} == 0);
	$href = {pmt_dsc=>$cols{$key}->{text},
		 credit=>$cols{$key}->{credit},
		 amount=>sprintf "%0.2f", $p->{$key}/100.0};
	if($href->{credit} ne "") {
	    $total -= $p->{$key};
	} else {
	    $total += $p->{$key};
	}

	if($config->{status} >= 3) {
	    my $tplf = new CGI::FastTemplate( $config->{templates} );
	    $tplf->define( footer => $config->{footer_pymt} );
	    $tplf->strict();
	    $tplf->assign($href);
	    $tplf->parse(MAIN => "footer");
	    $tplf->print();
	    $tplf = undef;
	}
    }

    $href = {total => sprintf("%0.2f", $arr[11]/100.0) };
    if(defined($tot_hash->{notes}) and $tot_hash->{notes} !~ /^\s*$/) {
	$href->{note} = $tot_hash->{notes};
    } else {
	$href->{NOTES} = "";
    }
    my $tplf = new CGI::FastTemplate( $config->{templates} );
    $tplf->define( footer => $config->{footer},
	notes => $config->{notes} );
    $tplf->strict();
    $tplf->assign($href);
    $tplf->parse(NOTES => "notes") if(defined($tot_hash->{notes}) and 
				      $tot_hash->{notes} !~ /^\s*$/);
    $tplf->parse(MAIN => "footer");
    $tplf->print();
    $tplf = undef;
}


# display an order for a member
# called after html heading has been output

sub display_mem_order {
    my ($config, $cgi, $dbh) = @_;
    set_titles($config, $cgi, $dbh);
    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    my $pr = get_products($config, $cgi, $dbh);
    print_html($pr, $config, $cgi, $dbh);
}

END { }       # module clean-up code here (global destructor)

1;
