#! /usr/bin/perl -w
# 
######################################################################
# This file is part of the Vokomokum Food Cooperative Administration.
#
# Vokomokum is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Vokomokum is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Vokomokum.  If not, see <http://www.gnu.org/licenses/>.
######################################################################


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
use Switch 'Perl6';
use voko;
use view_member;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $current_no;
my $status;
my $err_msgs = "";
my $config;
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

sub my_pids {
    my ($dbh) = @_;
    my %my_products;
    my %pids;
    my $st =
      'SELECT pr_id, meml_rcv FROM mem_line WHERE ord_no = ? AND mem_id = ?';
    my $sth = prepare($st, $dbh);
    $sth->execute($ord_no, $mem_id);
    while($a = $sth->fetchrow_arrayref) {
	$pids{$a->[0]} = $a->[1];
    }
    $sth->finish;
    return \%pids;
}

# get the product from the order file. Returns 4 hashes:
# shortages (prid->shortage, total_orders (prid->total member orders),
# total price of line item (prid->total_price), mem_price (prid->price)
sub get_shorts {
    my ($dbh) = @_;
    my %my_products;
    my %shorts;
    my %ordered;
    my %costs;
    my %price;
    my $pids = my_pids($dbh);

    my $mo_st =
      'SELECT pr_id, shortage, all_orders, price  FROM mo_view_all WHERE ord_no = ?';
    my $mo_sth = prepare($mo_st, $dbh);
    $mo_sth->execute($ord_no);
    while(my $a = $mo_sth->fetchrow_arrayref) {
	my $pr_id = $a->[0];
	$shorts{$pr_id}  = $a->[1] if($a->[1]);
	$ordered{$pr_id} = $a->[2];
	$price{$pr_id}   = $a->[3];
	$costs{$pr_id}  = "0.00";
	if(defined($pids->{$pr_id})) {
	    $costs{$pr_id}   = sprintf("%0.2f", $a->[3] * $pids->{$pr_id})
		if($pids->{$pr_id});
	   }
    }
    $mo_sth->finish;
    return (\%shorts, \%ordered, \%costs, \%price);
}

sub get_vars {
    my ($cgi, $dbh) = @_;
    my %pr_dat;
    my $vals = $cgi->Vars;
    my %new_vals;
    my %buttons;

    my $dump_data = {ip => $ENV{REMOTE_ADDR}, name => $config->{mem_name},
		     id => $mem_id, commit => $config->{committed},
		     time => scalar(localtime(time)) };

    if(not defined($vals) or not defined($vals->{order_no})) {
	# first entry, no selector, default is current order
	($config->{labels}, $config->{selector}) =
	    order_selector($ord_no, $ord_no, $dbh);
	if(not defined($vals)) {
	    dump_stuff("get_vars", "no_vals", "", $dump_data);
	    return (\%new_vals, \%buttons);
	}
	$vals->{order_no} = $current_no;
    }
    $dump_data->{none} = "";
    $dump_data->{some} = "";
    $dump_data->{cur_no} = $current_no;
    $dump_data->{ord_no} = $ord_no;

    if(defined($vals->{order_no})) {
	# we want a specific order
	$ord_no = $vals->{order_no};
	($config->{labels}, $config->{selector}) =
	    order_selector($current_no, $ord_no, $dbh);
	$status = 7 if($ord_no != $current_no);
    }

    $dump_data->{status} = $status;
    # inputs are - buttons: IncAll, IncOrd, Save, CommitOrd, CommitYes Reload
    # qty_nn qty
    # copy the buttons
    foreach my $but ( qw( IncAll IncOrd Save Commit SetDef CommitYes Reload)) {
	$dump_data->{$but} = (defined($vals->{$but})) ?
	    $vals->{$but} : "undef";
			      
	if (defined($vals->{$but})) {
	    $config->{all} = 0 if($but eq 'Reload');
	    $buttons{$but} = $vals->{$but};
	}
    }
    if($status <= 3) {

	foreach my $p (keys %{$vals}) {
	    my $q = $vals->{$p};
	    my $v = sprintf "%s:%s ", $p, $q;
	    next if($p !~ /^qty_\d+$/);
	    $p =~ s/qty_(\d+)/$1/;
	    $q =~ s/^\s*//;
	    $q =~ s/\s*$//;
	    $q = '0' if($q eq '');
	    if($q != 0) {
		$dump_data->{some} .= $v;
	    } else {
		$dump_data->{none} .= $v;
	    }
	    next if($q !~ /^\d+$/);
	    $new_vals{$p} = $q;
	}
    }
    dump_stuff("get_vars", "", "", $dump_data);

    return (\%new_vals, \%buttons);
}

# return an array of all voko products susbtitute quantities from
# new_vals where defined.
sub get_products {
    my ($new_vals, $cgi, $dbh) = @_;
    my $pids = my_pids($dbh);
    my ($shorts, $ordered, $cost, $price) = get_shorts($dbh);
    my @pr_ar;
    my %pr_hr;

    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    my $sth = prepare( 'SELECT * FROM product WHERE pr_active', $dbh );
    $sth->execute;

    while ( my $h = $sth->fetchrow_hashref ) {
    	my $pr_no = $h->{pr_id};
    	$h->{RowClass} = ( $ord_no != $current_no ) ? "myorder" : "editok";

    	if ( defined( $pids->{$pr_no} ) ) {
    	    $h->{order} =  $pids->{$pr_no};
    	    $h->{RowClass} = "myorder";
    	} else {
    	   $h->{order} = "0";
    	}

        if ( defined( $new_vals->{$pr_no} ) and $status < 3 ) {
            if ( $h->{order} != $new_vals->{$pr_no}
                 and $ord_no == $current_no )  {
		$h->{RowClass} = "editok";
		$new_vals->{unsaved} = 1;
            }
            $h->{order} = $new_vals->{$pr_no};
        }

    	$h->{pr_mem_price} =
            ( defined($price->{$pr_no})
              and ($ord_no != $current_no) )
    	    ? $price->{$pr_no} :
    	    sprintf "%0.2f", $h->{pr_mem_price}/100.0;
	$h->{meml_unit_price} = $h->{pr_mem_price};
        $h->{cost} =
            ( defined( $cost->{$pr_no} )
              and ( $ord_no != $current_no ) )
            ? $cost->{$pr_no} :
            sprintf( "%0.2f", $h->{order} * $h->{pr_mem_price} );

        if ( defined( $shorts->{$pr_no} )
    	     and $shorts->{$pr_no} != 0 ) {
    	    $h->{short} = $shorts->{$pr_no};
    	} else {
    	   $h->{short} = 0;
    	}

    	$h->{mem_qty} = ( defined($ordered->{$pr_no})) ? $ordered->{$pr_no} : 0;

    	$h->{pr_desc} = $cgi->escapeHTML( $h->{pr_desc} );
	$h->{pr_desc} =~ s/BULK/<B>BULK<\/B>/;
    	$pr_hr{$pr_no} = $h;

    	# display product if:
    	# config all is set - we've asked for everything
        #   or it's our product
        #   or it's short and we're doing adjustements and we've asked
        #   to see everything
	if ( $config->{all}
	     or defined( $pids->{$pr_no} )
	     or ( defined( $shorts->{$pr_no} ) and $config->{adjust} )
	     or ( defined( $new_vals->{$pr_no} ) and $new_vals->{$pr_no} != 0 ) ) {
	    push @pr_ar, $h;
	}
    }

    $sth->finish;
    my @sorted = sort pr_sort @pr_ar;

    return \@sorted, \%pr_hr;

}

# we've got the submitted variables. Get the current database state
# and apply any changed values
sub do_changes {
	
    my ($cgi, $dbh) = @_;
    my ($new_vals, $buttons) = get_vars($cgi, $dbh);
    # call get_products without passing new_vals, so we get the db values
    my ($pr_ar, $pr_hr) = get_products({}, $cgi, $dbh);

    # if new_vals is not empty, then we want to set the quantity of any item in 
    # 
    my $changes = 0;
    foreach my $pr_id (keys %{$new_vals}) {
	if(defined($pr_hr->{$pr_id})) {
	    my $h = $pr_hr->{$pr_id};
	    if($h->{order} != $new_vals->{$pr_id}) {
		$changes = 1;
		last;
	    }
	}
    }

    # $zeroise will be true if there are any entries in new_vals hash
    my $zeroise = scalar(keys (%{$new_vals}));

    # check that every product in db order with a non-zero quantity
    # has an entry from the submitted form. If not, create a dummy
    # form entry with a quantity of zero - this ensures all products
    # not displayed are being removed from the order
    if($status < 3  and $zeroise and ($ord_no == $current_no)) {
	foreach my $pr_id (keys %{$pr_hr}) {
	    my $h = $pr_hr->{$pr_id};
	    if(($h->{order} != 0) and
	       not defined($new_vals->{$pr_id})) {
		   $new_vals->{$pr_id} = 0;
		   $changes = 1;
	    }
	}
    }


    # now handle button updates - do commit if pressed and confirmed
    if(defined($buttons->{CommitYes}) and defined($buttons->{Commit}) and
       $buttons->{Commit} eq 'Commit' ) {
	my $sth = prepare('SELECT commit_order(?)', $dbh);
	eval {
	    $sth->execute($mem_id);
	    $sth->fetchrow_arrayref;
	};
	if($@) {
	    my $e = $@;
	    $e =~ s/.*ERROR: *//;
	    $e =~ s/\sat \/.*$//;

	    if(length($err_msgs) == 0) {
		my $tpl = new CGI::FastTemplate($config->{templates});
		$tpl->strict();
		$tpl->define( emsg  => "common/err_pr_title.template");
		my %em = (err_msg => $e);
		$tpl->assign(\%em);
		$tpl->parse(MAIN => "emsg");
		my $e = $tpl->fetch("MAIN");
		$err_msgs = $$e;
		$tpl = undef;
	    }

	    $dbh->rollback();
	} else {
	    $config->{committed} = 1;
	    $dbh->commit;
	}
    }

    if(not defined($buttons->{Reload}) and
       (($status == 2 and not $config->{committed} and $changes) or 
	# changed or not, not committed, commit pressed but not confirmed
	(not $config->{committed} and defined($buttons->{Commit})
	    and ($buttons->{Commit} eq 'Commit')
	    and not defined($buttons->{CommitYes})))) {
	my $tpl = new CGI::FastTemplate($config->{templates});
	$tpl->strict();
	$tpl->define( emsg      => "common/err_pr_title.template");
	my %em = (err_msg => ($config->{committed}) ?
		  'You did not tick the agreement, your order is not changed' :
		  'You did not tick the agreement, your order is not yet committed');
	$tpl->assign(\%em);
	$tpl->parse(MAIN => "emsg");
	my $e = $tpl->fetch("MAIN");
	$err_msgs = $$e . $err_msgs;
	$tpl = undef;
    } elsif(not defined($buttons->{Reload})) {
	# attempt to apply changes
	my $add_errors = 1;
	foreach my $pr_id (keys %{$new_vals}) {
	    last if(! $changes);
	    if(defined($pr_hr->{$pr_id})) {
		my $h = $pr_hr->{$pr_id};
		my $old_val = $h->{order};
		if($h->{order} != $new_vals->{$pr_id}) {
		    my $sth = prepare('SELECT add_order_to_member(?, ?, ?, 0)',
				      $dbh);
		    eval {
			$sth->execute($pr_id, $new_vals->{$pr_id}, $mem_id);
			$sth->fetchrow_arrayref;
		    };
		    if($@) {
			my $e = $@;
			$e =~ s/.*ERROR: *//;
                        $e =~ s/\sat \/.*$//;

			if(length($err_msgs) == 0) {
			    my $tpl = new CGI::FastTemplate($config->{templates});
			    $tpl->strict();
			    $tpl->define( emsg      => "common/err_pr_title.template");
			    my %em = (err_msg => $e);
			    $tpl->assign(\%em);
			    $tpl->parse(MAIN => "emsg");

			    my $e =  $tpl->fetch("MAIN");
			    $err_msgs = $$e;
			    $tpl = undef;
		        }
			syslog(LOG_ERR, sprintf("add_order_to member(%s, %s, %s) failed with message %s, rolling back", $pr_id, $new_vals->{$pr_id}, $mem_id, $e));
		        $dbh->rollback();
			#dump_stuff("errors", "$old_val", "$h->{order}", $h);
			#dump_stuff("", "", "", $new_vals->{$pr_id});			
		        $h->{order} = $new_vals->{$pr_id};
			my $tplr = new CGI::FastTemplate($config->{templates});
			$tplr->define(row => "mem_order/error-row.template");
			$tplr->assign($h);
			$tplr->parse(MAIN => "row");
			$e = $tplr->fetch("MAIN");
			$err_msgs .= $$e;
			$tplr = undef;
			$new_vals->{$pr_id} = $old_val;
		    } else {
			$dbh->commit;
		    }
		}
	    }
	}

    }

    # set default orders
    if(defined($buttons->{SetDef}) and $buttons->{SetDef} =~ "Set") {
	my $sth = prepare('SELECT create_default_order(?, ?)', $dbh);
	eval {
	    $sth->execute($mem_id, $ord_no);
	    $sth->fetchrow_arrayref;
	};
	if($@) {
	    my $e = $@;
	    $e =~ s/.*ERROR: *//;
	    $e =~ s/\sat \/.*$//;
	    if(length($err_msgs) == 0) {
		my $tpl = new CGI::FastTemplate($config->{templates});
		$tpl->strict();
		$tpl->define( emsg      => ".common/err_pr_title.template");
		my %em = (err_msg => $e);
		$tpl->assign(\%em);
		$tpl->parse(MAIN => "emsg");
		my $em = $tpl->fetch("MAIN");
		$err_msgs = $$em;
		$tpl = undef;
	    }
	    syslog(LOG_ERR, "create_default_order($mem_id, $ord_no) failed with message $e, rolling back");

	    $dbh->rollback();
	} else {
            $err_msgs = '<p älign ="center">This is now your default order</p><p/>';
	    $dbh->commit;
	}
    }

    # set up headings and such like

    $config->{col_hdr} = ($config->{all}) ?
	"mem_order/all-titles.template" : "common/titles.template";
    $config->{sub_cat_hdr} = ($config->{all}) ?
	"mem_order/all-sub_cat.template" : "common/sub_cat.template";
	
    if ( $status < 2 or ($status == 2 and not $config->{committed})) {
    	if (defined( $buttons->{Reload} )
    	    or not $config->{all}) {
	    $config->{title} = "My Orders";
    	    $config->{nextcgi}  = "/cgi-bin/mem_order.cgi";

    	} else {
	    $config->{title} = "My Current Order";
    	    $config->{nextcgi}  = "/cgi-bin/all-order";
	}

    	$config->{title}   .= " (Committed)" if ( $config->{committed} );
    	$config->{buttons}  = "mem_order/save_ord.template";
    	$config->{row}	    = "mem_order/editprrow.template";
		
    	$config->{footer}   = ( $status > 0 and not $config->{committed})
				? "mem_order/footer-commit.template"
				: "mem_order/footer-save.template";
	
    } elsif( $status == 2 ) {
	
		
    	if (defined( $buttons->{Reload} )
    	    or not $config->{all}) {
    	    $config->{title} = "Reduce Shortages/View Current Order";
    	    $config->{nextcgi}  = "/cgi-bin/mem_order.cgi";
    	} else {
    	    $config->{title} = "Add Items/Reduce Shortages On Current Order";
    	    $config->{nextcgi}  = "/cgi-bin/all-order";
    	}

    	$config->{title} .= " (Committed)" if ( $config->{committed} );
    	$config->{buttons} = "mem_order/nosave_ord.template";
    	$config->{row}      = "mem_order/editprrow.template";
    	$config->{footer}   = "mem_order/footer-save.template";
		
    } else {
	if($config->{all}) {
	    $config->{title} .= "Product List";
	    $config->{buttons} = "mem_order/view_products_buttons.template";
	    $config->{row}      = "mem_order/view_products_row.template";
	    $config->{footer}   = "mem_order/view_products_footer.template";
    	    $config->{nextcgi}  = "/cgi-bin/all-order";
	    $config->{col_hdr}	= "mem_order/view_products_titles.template";
	    $config->{sub_col_hdr} = "mem_order/all_sub_cat.template";
	} else {
	    $config->{title}	= "$config->{labels}->{$ord_no} Order";
	    $config->{nextcgi}	= "/cgi-bin/mem_order.cgi";
	    $config->{buttons}	= "mem_order/no-buttons.template";
	    $config->{all}    	= 0;
	    $config->{col_hdr}	= "common/mem_order_cols.template";
	    $config->{sub_col_hdr} = "mem_order/all_sub_cat.template";
	    $config->{row}   	= "common/mem_order_row.template";
	    $config->{footer}	= "common/mem_order_footer.template";
	}
    }

    return ($new_vals, $buttons);
	
}

sub print_html {
    my ($pr, $new_vals, $buttons, $config, $cgi, $dbh) = @_;

    #dump_stuff("print_html", "pr", "", $pr);
    #dump_stuff("print_html", "new_vals", "", $new_vals);

    $err_msgs .= '<h3 align="center">Rows marked in blue are unsaved changes</ddh3>'
	if(defined($new_vals->{unsaved}) and ($ord_no == $current_no));

    # total the order before display
    my $total = 0;
    if($status == 7) {
	$total = get_ord_totals($mem_id, $ord_no, $dbh)->[-1];
	$dbh->commit;
    } else {
	foreach my $h (@{$pr}) {
	    if($h->{mem_no} = $mem_id){
		$total += $h->{cost};
	    }
	}
    }
	
    # and convert from eurocents to euros
    $total = sprintf("%0.2f", $total);
	
    my $tpl = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();
    $tpl->define(header => "common/header.template",
		 banner => ( $config->{is_admin} )
		 ? "common/adm-banner.template"
		 : "common/mem-banner.template",
		 cats => "common/category-links.template",
		 prbuttons => $config->{buttons},
		 subtitle => $config->{subtitle}
    );

    my %hdr_h = (
	Pagename    => $config->{title},
	Title	    => $config->{title},
	Nextcgi	    => $config->{nextcgi},
	IncOrdTxt   => "Show only items in my order",
	mem_name    => $config->{mem_name},
	LINKS	    => get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh),
	total	    => $total,

	);

    $hdr_h{DROP} = ($config->{all}) ? "&nbsp" : $config->{selector};
    $hdr_h{LINKS} = "" if ( not $config->{all} );

    $tpl->assign(\%hdr_h);
    $tpl->parse( STUFF => "prbuttons" );
    $tpl->parse( BUTTONS => "cats" );
    # $tpl->parse( SUBTITLE => "subtitle" );
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse( MAIN => "header" );
    $tpl->print( "MAIN" );

    print "$err_msgs<p/>" if(length($err_msgs) > 0);
    my $last_cat = -1;
    my $last_sc = -1;
    my $line = 0;

    #print '<table class="main">';

    # use the view_member.pm routines if it's not editable
    # (assures one code source for all non-editing routines)

    if($status == 7 and not $config->{all}) {
	$config->{status} = $status;
	$config->{ord_no} = $ord_no;
	$config->{mem_id} = $mem_id;
	display_mem_order($config, $cgi, $dbh);
	return;
    }

    foreach my $h ( @{$pr} ) {
    	if ( $config->{all} ) {
    	    if ( $last_cat != $h->{pr_cat} ) {
		$last_cat = $h->{pr_cat};
	        $last_sc = 99999;
		print_title(
                    "$config->{col_hdr}",
                    $last_cat,
		    $categories{$last_cat},
                    $cat_descs{$last_cat},
                    $config
                );
    	    }
	    if ( $last_sc != $h->{pr_sc} ) {
		$last_sc = $h->{pr_sc};
		print_sub_cat($config->{sub_cat_hdr}, $last_cat,
			      $last_sc, \%sc_descs, $config);
	    };
    	} else {
    	    next if ( $h->{order} == 0 );
    	    if ( ( $line++ % 20 ) == 0 ) {
		my $tpt = new CGI::FastTemplate( $config->{templates} );
		$tpt->define( line => $config->{col_hdr} );
		$tpt->assign( {Description => "Description"} );
		$tpt->parse( MAIN => "line" );
		$tpt->print( "MAIN" );
		$tpt = undef;
    	    }
    	}

	$h->{sh_color} = ($h->{short}) ? 'bgcolor="pink"><B' : '';
    	my $tplr = new CGI::FastTemplate( $config->{templates} );
	my $url_temp = "common/dnb_url.template";
	if ( $h->{pr_wh} == $config->{DNB}->{dnb_wh_id} ) {
            if ( $h->{wh_prcode} < 10000 ) {
                $h->{PID} = sprintf "%04.4d", $h->{wh_prcode};
            } else {
		$h->{PID} =  $h->{wh_prcode};
	    }
	} elsif($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BG}->{bg_wh_id} and 
		$config->{BG}->{$h->{pr_id}}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{BG}->{$h->{pr_id}};
	} else {
	    $url_temp = "common/no_url.template";
	    $h->{URL} = "";
	}

	$tplr->define(row => $config->{row},
		     url => $url_temp);
	$tplr->assign($h);
	$tplr->parse("URL", "url");
	    
    	$tplr->parse( MAIN => "row" );
    	$tplr->print();
    	$tplr = undef;
	
    }

    if ( $line++ == 0 ) {
	my $tpt = new CGI::FastTemplate( $config->{templates} );
	$tpt->define( line => $config->{col_hdr} );
	$tpt->assign( {Description => "Description", Name=>""} );
	$tpt->parse( MAIN => "line" );
	$tpt->print( "MAIN" );
	$tpt = undef;
    }

    my $tplf = new CGI::FastTemplate( $config->{templates} );
    $tplf->define( footer => $config->{footer} );
		
    my %tots = (total  => $total,
		CommitTxt => "Commit This Order");
    $tots{NOTES} = "";
    $tplf->assign(\%tots);
    $tplf->parse(MAIN => "footer");
    $tplf->print();
    $tplf = undef;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my ($new_vals, $buttons) = do_changes($cgi, $dbh);
    my ($pr, $hr) = get_products($new_vals, $cgi, $dbh);
    print_html($pr, $new_vals, $buttons, $config, $cgi, $dbh);
}


sub main {
    my $program = $0;
    $program =~ s/.*\///;
    $config = read_conf($conf);
    $config->{caller} = $program;
    $config->{program} = $program;
    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "$program");

    my ($cgi, $dbh) = open_cgi($config);
    my $vals = $cgi->Vars;

    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	$mem_id = process_login(0, $config, $cgi, $dbh);
    } else {
	$mem_id = handle_cookie(0, $config, $cgi, $dbh);
    }

    $current_no = $ord_no;
    my $sth = prepare('SELECT memo_commit_closed IS NOT NULL ' .
		   'FROM mem_order WHERE mem_id = ? AND ord_no = ?', $dbh);
    $sth->execute($mem_id, $ord_no);
    my $aref = $sth->fetchrow_arrayref;
    $config->{committed} = (defined($aref) and $aref->[0] ne '0') ? 1 : 0;
    # we don't allow order activity if status is 2 and the member
    # does not have a committed order. The crude hack is to pretend
    # the status is 4 (order closed and on it's way to wholesaler)
    #$status = 4 if(not $config->{committed} and $status == 2);
    $sth->finish;

    $config->{all} = ($program =~ /^all/);
    if($status == 3) {
	# allow product orders for admin special account. Crude hack
	$sth = prepare('SELECT mem_adm_adj FROM members WHERE mem_id=?',
		       $dbh);
	$sth->execute($mem_id);
	my $h = $sth->fetchrow_hashref;
	$sth->finish;
	$dbh->commit;
	$status = 2 if(defined($h) and $h->{mem_adm_adj});
    }
    $config->{adjust} = ($status == 3 or $status == 6);

    doit($config, $cgi, $dbh);

	$dbh->disconnect;
    exit 0;

}
main;
