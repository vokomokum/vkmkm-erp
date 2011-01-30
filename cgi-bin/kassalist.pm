#!/usr/bin/perl

# --------------------------------------
# Call this script to generate pickup lists
# (in your browsaer and for our files)
# --------------------------------------

package voko;
use strict;
use warnings;

use Config::General;
use Data::Dumper;
use DBI;
use CGI::FastTemplate;
use CGI::Pretty qw(:standard);
use CGI qw/escape unescape/;
use CGI::Carp 'fatalsToBrowser';
use Unix::Syslog qw( :macros :subs );
use POSIX qw(strftime);
use MIME::Base64;
use Crypt::PasswdMD5;
use voko;

BEGIN {
    use Exporter   ();
    our ($VERSION, @ISA, @EXPORT, @EXPORT_OK, %EXPORT_TAGS);

    $VERSION     = sprintf "%d.%03d", q$Revision: 1.1 $ =~ /(\d+)/g;

    @ISA         = qw(Exporter);
    @EXPORT      = qw(print_pickup_lists);
    %EXPORT_TAGS = ( );     # eg: TAG => [ qw!name1 name2! ],
    @EXPORT_OK   = ();
}
our @EXPORT_OK;


# -- globals --
my $err_msgs = "";
my $order_name = "Current";

sub get_kassa_list_data{
    my ($config, $dbh) = @_;
    
    my %kassa_list = (); # a hash, containing name, price and btw sums for each member id
    my $all_price = 0;
    my $all_btw = 0;
    my $all_statiegeld_in = 0;
    my $all_statiegeld_out = 0;
    my $all_crates_in = 0;
    my $all_crates_out = 0;
    my $all_misc_in = 0;
    my $all_misc_out = 0;
    my $all_membership = 0;
    my $all_tot  = 0;
    my $all_missing = 0;
    my $all_damaged = 0;
    my $all_vers = 0;
    my $all_total = 0;

    # find members and the number of their order items we need to list
    my $st = 'SELECT m.mem_id, m.mem_lname, join_name(m.mem_fname, m.mem_prefix, '.
        'm.mem_lname) as mem_name, mo.mo_stgeld_rxed, mo.mo_stgeld_refunded, '.
	'mo,mo_stgeld_refunded, mo.mo_crates_rxed, mo.mo_crates_refunded, mo.mo_vers, ' .
	'mo.mo_misc_rxed, mo.mo_misc_refunded, mo.ord_label, mo.mo_membership FROM members m, '.
        'mem_order mo WHERE mo.ord_no = ? AND m.mem_id = mo.mem_id';
    my $mem_details = prepare($st, $dbh);

    my $mis_sth = prepare("SELECT sum(meml_missing * meml_ex_btw) as missing, ".
			  "sum(meml_damaged * meml_ex_btw) as damaged FROM ".
			  "mem_line WHERE ord_no = ? AND mem_id = ?", $dbh);
    
    $mem_details->execute($config->{ord_no});
    # loop through all members
    my ($mem_price, $mem_btw, $mem_tot, $statiegeld_in_sum, $crates_in_sum, $misc_in_sum, 
	$statiegeld_out_sum, $crates_out_sum, $misc_out_sum, $membership_sum, $mem_vers_sum);
    while(my $mem = $mem_details->fetchrow_hashref) {
	# unlock mem_order table so we can get the order totals
	$dbh->commit;
	$order_name = $mem->{ord_label} if(defined($mem->{ord_label}));
        my $totref = get_ord_totals($mem->{mem_id}, $config->{ord_no}, $dbh);

        $all_price += $mem_price = $totref->[-3];
        $all_btw += $mem_btw = $totref->[-2];
	$all_total += $mem_tot = $totref->[-1];
	$all_statiegeld_in += $statiegeld_in_sum = $mem->{mo_stgeld_rxed};
	$all_statiegeld_out += $statiegeld_out_sum = -$mem->{mo_stgeld_refunded};
	$all_crates_in += $crates_in_sum = $mem->{mo_crates_rxed};
	$all_crates_out += $crates_out_sum = -$mem->{mo_crates_refunded};
	$all_misc_in += $misc_in_sum = $mem->{mo_misc_rxed};
	$all_misc_out += $misc_out_sum = -$mem->{mo_misc_refunded} ;
	$all_membership += $membership_sum = $mem->{mo_membership};
	$all_vers += $mem_vers_sum = $mem->{mo_vers};
	$mis_sth->execute($config->{ord_no}, $mem->{mem_id});
	my $href = $mis_sth->fetchrow_hashref;
	$href = {missing => 0, damaged => 0} if(not defined($href) or 
						not defined($href->{missing}));
	$all_missing -= $href->{missing};
	$all_damaged -= $href->{damaged};

	next if($mem_price == 0 and $mem_btw == 0 and $href->{missing} == 0 and 
		$href->{damaged} == 0 and $crates_in_sum == 0 and $crates_out_sum == 0
		and $statiegeld_in_sum == 0 and $statiegeld_out_sum == 0 and
		$misc_in_sum == 0 and $misc_out_sum == 0 and $membership_sum == 0 and
		$mem_vers_sum == 0 and $mem_tot == 0);
        $kassa_list{mems}->{$mem->{mem_lname}} = {
	    ord_num        => $config->{ord_no},
	    mem_id         => $mem->{mem_id},
	    name           => $mem->{mem_name}, 
	    price          => $mem_price, 
	    btw            => $mem_btw, 
	    missing        => -$href->{missing},
	    damaged        => -$href->{damaged},
	    statiegeld_in  => $statiegeld_in_sum, 
	    crates_in      => $crates_in_sum, 
	    misc_in        => $misc_in_sum,
	    statiegeld_out => $statiegeld_out_sum, 
	    crates_out     => $crates_out_sum, 
	    misc_out       => $misc_out_sum,
	    membership     => $membership_sum,
	    vers           => $mem_vers_sum,
	    total          => $mem_tot,
	};
						    
    } 
    $mis_sth->finish;
    $mem_details->finish;
    $dbh->commit;
    $kassa_list{"all"} = {
	mem_id         => "",
	name           => 'Totals',
	price          => $all_price, 
	btw            => $all_btw, 
	missing        => $all_missing,
	damaged        => $all_damaged,
	statiegeld_in  => $all_statiegeld_in,
	crates_in      => $all_crates_in, 
	misc_in        => $all_misc_in,
	statiegeld_out => $all_statiegeld_out,
	crates_out     => $all_crates_out, 
	misc_out       => $all_misc_out,
	membership     => $all_membership,
	vers           => $all_vers,
	total          => $all_total,
    };

    return %kassa_list;
}

# get wholesale data for an order
# for each wholesaler, get the wholesaler costs:
#     ex-btw total, total btw, grand_total
#     and the member receipts:
#     ex_btw total, missing, damaged
#     we don;t get the member btw, as it may be spread over multiple wholesalers                        
# summary will be:
# ex-btw,  btw, total to wholesalers -members ex-btw members-btw btw-owed 

sub get_wholesale_data {
    my ($config, $dbh) = @_;

    my @wh_ids;
    my $h;
    my $sth = prepare("SELECT wh_id FROM wh_order WHERE ord_no = ?", $dbh);
    $sth->execute($config->{ord_no});
    push @wh_ids, $h->{wh_id} while($h = $sth->fetchrow_hashref);
    $sth->finish;

    # get all the individual wholesaler total ex-btw, total btw, grand total
    $sth = prepare("SELECT sum(tot) AS ex_btw, sum(tot * btw) AS btw  ".
		      "FROM (SELECT ".
		      "sum(whl_rcv * whl_price) AS tot, whl_btw AS btw ".
		      "FROM wh_line WHERE ord_no = ? AND wh_id = ? GROUP BY ".
		      "whl_btw) as f", $dbh);
    my $mem_sth = prepare("SELECT sum(m.meml_pickup * m.meml_ex_btw) AS mem_tot, ".
			  "sum(m.meml_missing * m.meml_ex_btw) as missing, ".
			  "sum(m.meml_damaged * m.meml_ex_btw) as damaged FROM ".
			  "mem_line AS m, product AS p WHERE m.ord_no = ? ".
			  "AND p.pr_id = m.pr_id and p.pr_wh = ?", $dbh);

    my $all_ex_btw = 0;
    my $all_btw = 0;
    my $all_total = 0;
    my $all_mem_total = 0;
    my $all_missing = 0;
    my $all_damaged = 0;
    my %wh_tots;

    foreach my $wh (@wh_ids) {
	$sth->execute($config->{ord_no}, $wh);
	$h = $sth->fetchrow_hashref;
	$all_ex_btw += $h->{ex_btw};
	$all_btw    += $h->{btw} = int($h->{btw} / 100);
	$all_total  += $h->{total} = $h->{ex_btw} + $h->{btw};
	$h->{mem_tot} = 0;
	$h->{missing} = 0;
	$h->{damaged} = 0;
	$mem_sth->execute($config->{ord_no}, $wh);
	my $mh = $mem_sth->fetchrow_hashref;
	if(defined($mh)) {
	    $h->{mem_tot} = $mh->{mem_tot}; 
	    $h->{missing} = $mh->{missing}; 
	    $h->{damaged} = $mh->{damaged}; 
	}
    
	$all_mem_total += $h->{mem_tot};
	$all_missing += $h->{missing};
	$all_damaged += $h->{damaged};
	$wh_tots{wh_id}->{$wh} = $h;
    }
    $mem_sth->finish;
    $sth->finish;
    $dbh->commit;
    
    $wh_tots{all}= {ex_btw  => $all_ex_btw,
		    btw     => $all_btw,
		    total   => $all_total,
		    mem_tot => $all_mem_total,
		    missing => $all_missing,
		    damaged => $all_damaged,
    };
    return %wh_tots;
}

sub print_html_kassa_list{
    my ($config, $dbh) = @_;

    my $value;

    my %kassa = get_kassa_list_data($config, $dbh);
    my %wh_tots = get_wholesale_data($config, $dbh);
    $wh_tots{all}->{mem_ex_btw} = $kassa{all}->{price} - $kassa{all}->{btw};
    $wh_tots{all}->{mem_btw}    = $kassa{all}->{btw};
    $wh_tots{all}->{mem_tot}    = $kassa{all}->{price};
    $wh_tots{all}->{btw_due}    = $wh_tots{all}->{btw} - $kassa{all}->{btw};
    $wh_tots{all}->{margin}     = $wh_tots{all}->{mem_ex_btw} - $wh_tots{all}->{ex_btw} +
	$wh_tots{all}->{btw_due};
    $wh_tots{all}->{prc_marg} = int(10000 * $wh_tots{all}->{margin} / 
	$wh_tots{all}->{mem_tot});

    # dump_stuff("print html", "", "", \%wh_tots);
	
    my $tplh = new CGI::FastTemplate($config->{templates});
    $tplh->strict();
    $tplh->define( header  => "common/header.template",
	           banner  => "common/adm-banner.template",
	           buttons => "kassalist/mem_table_header.template");
    my $h = { 
	Pagename   => "Kassalist for Order $order_name",
	Title      => "Kassalist for Order $order_name",
	Nextcgi    => "kassalist.pm",
	DROP       => $config->{selector},
	mem_name    => escapeHTML($config->{mem_name}),
    };
    $tplh->assign($h);
    $tplh->parse(BUTTONS => "buttons");
    admin_banner($config->{status}, "BANNER", "banner", $tplh, $config);
    $tplh->parse(BANNER => "banner");
    $tplh->parse(MAIN => "header");
    $tplh->print("MAIN");

    my $fname_dp = "/kassa/kassalist-${order_name}_dp.csv";
    my $fname_com = "/kassa/kassalist-${order_name}_com.csv";
    open(my $fh, "> ../data$fname_dp") or die "Can't open kassalist file $fname_dp: $!";
    open(my $fh_com, "> ../data$fname_com") or die "Can't open kassalist file $fname_com: $!";
    $tplh = new CGI::FastTemplate($config->{templates});
    $tplh->strict();
    $tplh->define( header  => "kassalist/csv_mem_table_header.template");
    $tplh->assign($h);
    $tplh->parse(MAIN => "header");
    my $prref = $tplh->fetch("MAIN");
    my $pr = $$prref;
    print $fh $pr;
    $pr =~ s/\./,/g;
    print $fh_com $pr;

    foreach my $key (sort {lc($a) cmp lc($b)} (keys (%{$kassa{mems}}))) {
        $value = $kassa{mems}->{$key};
	foreach my $f (qw(price btw missing damaged statiegeld_in
			  statiegeld_out crates_in crates_out
			   misc_in misc_out membership  vers total)) {
	    $value->{$f} = sprintf("%.2f", $value->{$f}/100.0);
	}
	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->strict();
        $tplr->define(row => "kassalist/csv_mem_row.template", );
        $tplr->assign($value);
        $tplr->parse(MAIN => "row");
	$prref = $tplr->fetch("MAIN");
	$pr = $$prref;
	print $fh $pr;
	$pr =~ s/\./,/g;
	print $fh_com $pr;
	   
	foreach my $f (qw(price btw missing damaged statiegeld 
			  crates misc total)) {
	    if(defined($value->{$f}) and $value->{$f} < 0) {
		$value->{$f} = "<font color='red'><B>$value->{$f}</B></font>";
	    }
	}
	$value->{name} = escapeHTML($value->{name});
	$tplr = new CGI::FastTemplate($config->{templates});
	$tplr->strict();
	$tplr->define(row => "kassalist/mem_row.template", );
	$tplr->assign($value);
	$tplr->parse(MAIN => "row");
	$tplr->print("MAIN");
	
    }

    $value = $kassa{all};
    foreach my $f (qw(price btw missing damaged statiegeld_in statiegeld_out 
		      crates_in crates_out misc_in misc_out membership vers total)) {
	$value->{$f} = sprintf("%.2f", $value->{$f}/100.0);
    }
    my $tplt = new CGI::FastTemplate($config->{templates});
    $tplt->strict();
    $tplt->define(row => "kassalist/csv_mem_row.template", );
    $tplt->assign($value);
    $tplt->parse(MAIN => "row");
    $prref = $tplt->fetch("MAIN");
    $pr = $$prref;
    print $fh $pr;
    $pr =~ s/\./,/g;
    print $fh_com $pr;

    foreach my $f (qw(price btw missing damaged statiegeld 
		      crates misc total)) {
	if(defined($value->{$f}) and $value->{$f} < 0.0) {
	    $value->{$f} = "<font color='red'><B>$value->{$f}</B></font>";
	}
    }
    
    $tplt = new CGI::FastTemplate($config->{templates});
    $tplt->strict();
    $tplt->define(
	total => "kassalist/totals_row.template", 
	row   => "kassalist/mem_row.template", 
	);
    $tplt->assign($value);
    $tplt->parse(ROW  => "row");
    $tplt->parse(MAIN => "total");
    $tplt->print("MAIN");

    
    close($fh);
    close $fh_com;

    my $tplf = new CGI::FastTemplate($config->{templates});
    $tplf->strict();
    $tplf->define(
	row   => "kassalist/mem_footer.template", 
	);
    $tplf->assign({filename_en => $fname_dp,
		  filename_nl => $fname_com});
    $tplf->parse(MAIN => "row");
    $tplf->print("MAIN");

    $dbh->disconnect;
    exit 0;
}


# --------- copied from some other module, we might not need all of this 
# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $status;
my $conf = "../passwords/db.conf";
sub main {	     
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);

    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;

    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "Running as $program");

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    my $vals = $cgi->Vars;
    if(defined($vals->{order_no})) {
	# we want a specific order
	$ord_no = $vals->{order_no};
    }

    ($config->{labels}, $config->{selector}) = 
	order_selector($config->{ord_no},  $ord_no, $dbh);
    $config->{ord_no} = $ord_no;
    print_html_kassa_list($config, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
# -----------

END { }       # module clean-up code here (global destructor)
1;
