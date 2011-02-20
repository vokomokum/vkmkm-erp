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
    my $all_statiegeld_in = 0;
    my $all_statiegeld_out = 0;
    my $all_crates_in = 0;
    my $all_crates_out = 0;
    my $all_misc_in = 0;
    my $all_misc_out = 0;
    my $all_membership = 0;
    my $all_missing = 0;
    my $all_damaged = 0;
    my $all_vers_g = 0;
    my $all_vers_k = 0;
    my $all_vers_m = 0;
    $kassa_list{all} = {wh_exbtw=>0, wh_btw=>0, wh_tot=>0, mem_exbtw=>0, mem_btw=>0, mem_tot=>0};

    # find members and the number of their order items we need to list
    my $st = 'SELECT m.mem_id, m.mem_lname, join_name(m.mem_fname, m.mem_prefix, '.
        'm.mem_lname) as mem_name, mo.mo_stgeld_rxed, mo.mo_stgeld_refunded, '.
	'mo,mo_stgeld_refunded, mo.mo_crates_rxed, mo.mo_crates_refunded, ' .
	'mo.mo_vers_groente, mo.mo_vers_kaas, mo.mo_vers_misc, ' .
	'mo.mo_misc_rxed, mo.mo_misc_refunded, mo.ord_label, mo.mo_membership FROM members m, '.
        'mem_order mo WHERE mo.ord_no = ? AND m.mem_id = mo.mem_id';
    my $mem_details = prepare($st, $dbh);

    # get wholesale part and missing/damaged item amounts in terms of wholesale price and wholesaler's btw
    my $mem_sth = prepare("SELECT CAST(sum(wh_total)/ 100 AS INTEGER) AS wh_tot, " .
			  "CAST(sum(wh_missing)/ 100 AS INTEGER) AS missing, " .
			  "CAST(sum(wh_exbtw)/ 100 AS INTEGER) AS wh_exbtw, " .
			  "CAST(sum(wh_btw)/ 100 AS INTEGER) AS wh_btw, " .
			  "CAST(sum(wh_damaged)/100 AS INTEGER) AS damaged FROM (SELECT " .
			  "(m.meml_pickup * p.pr_wh_price * (100.0 + p.pr_btw)/p.pr_wh_q) AS wh_total, " .
			  "(m.meml_pickup * p.pr_wh_price * 100.0/p.pr_wh_q) AS wh_exbtw, " .
			  "(m.meml_pickup * p.pr_wh_price * p.pr_btw/p.pr_wh_q) AS wh_btw, " .
			  "(m.meml_missing * p.pr_wh_price * (100 + p.pr_btw)/p.pr_wh_q) AS wh_missing, " .
			  "(m.meml_damaged * p.pr_wh_price * (100 + p.pr_btw)/p.pr_wh_q) AS wh_damaged " .
			  "FROM product as p, mem_line as m  WHERE p.pr_id = m.pr_id " .
			  "AND  m.ord_no = ? AND  m.mem_id = ? ) AS wh", $dbh);

    $mem_details->execute($config->{ord_no});
    # loop through all members
    my ($wh_exbtw, $wh_btw, $wh_tot, $mem_exbtw, $mem_btw, $mem_tot, $statiegeld_in_sum, 
	$crates_in_sum, $misc_in_sum, $statiegeld_out_sum, $crates_out_sum, $misc_out_sum, 
	$membership_sum, $mem_vers_g_sum, $mem_vers_k_sum, $mem_vers_m_sum);

    while(my $mem = $mem_details->fetchrow_hashref) {
	# unlock mem_order table so we can get the order totals
	$dbh->commit;
	$order_name = $mem->{ord_label} if(defined($mem->{ord_label}));

        my $totref = get_ord_totals($mem->{mem_id}, $config->{ord_no}, $dbh);

	$mem_sth->execute($config->{ord_no}, $mem->{mem_id});
	my $href = $mem_sth->fetchrow_hashref;
	if(not $href or !defined($href->{wh_exbtw})) {
	    $href = {wh_tot=>0, missing=>0, wh_exbtw=>0, wh_btw=>0, damaged=>0};
	}
	
	$all_missing -= $href->{missing};
	$all_damaged -= $href->{damaged};
	$mem_tot = $totref->[-1];
	$mem_exbtw = $totref->[-3];
	$mem_btw = $totref->[-2];
	$all_statiegeld_in += $statiegeld_in_sum = $mem->{mo_stgeld_rxed};
	$all_statiegeld_out += $statiegeld_out_sum = -$mem->{mo_stgeld_refunded};
	$all_crates_in += $crates_in_sum = $mem->{mo_crates_rxed};
	$all_crates_out += $crates_out_sum = -$mem->{mo_crates_refunded};
	$all_misc_in += $misc_in_sum = $mem->{mo_misc_rxed};
	$all_misc_out += $misc_out_sum = -$mem->{mo_misc_refunded} ;
	$all_membership += $membership_sum = $mem->{mo_membership};
	$all_vers_g += $mem_vers_g_sum = $mem->{mo_vers_groente};
	$all_vers_k += $mem_vers_k_sum = $mem->{mo_vers_kaas};
	$all_vers_m += $mem_vers_m_sum = $mem->{mo_vers_misc};
	$mem_sth->execute($config->{ord_no}, $mem->{mem_id});
	
	next if($mem_tot == 0 and $href->{missing} == 0 and 
		$href->{damaged} == 0 and $crates_in_sum == 0 and $crates_out_sum == 0
		and $statiegeld_in_sum == 0 and $statiegeld_out_sum == 0 and
		$misc_in_sum == 0 and $misc_out_sum == 0 and $membership_sum == 0 and
		$mem_vers_g_sum == 0 and $mem_vers_k_sum == 0 and $mem_vers_m_sum == 0);
        $kassa_list{mems}->{$mem->{mem_lname}} = {
	    ord_num        => $config->{ord_no},
	    mem_id         => $mem->{mem_id},
	    name           => $mem->{mem_name}, 
	    wh_exbtw       => $href->{wh_exbtw}, 
	    wh_btw         => $href->{wh_btw}, 
	    wh_tot         => $href->{wh_tot},
	    missing        => -$href->{missing},
	    damaged        => -$href->{damaged},
	    statiegeld_in  => $statiegeld_in_sum, 
	    crates_in      => $crates_in_sum, 
	    misc_in        => $misc_in_sum,
	    statiegeld_out => $statiegeld_out_sum, 
	    crates_out     => $crates_out_sum, 
	    misc_out       => $misc_out_sum,
	    membership     => $membership_sum,
	    vers_g         => $mem_vers_g_sum,
	    vers_k         => $mem_vers_k_sum,
	    vers_m         => $mem_vers_m_sum,
	    mem_exbtw      => $mem_exbtw,
	    mem_btw        => $mem_btw,
	    mem_tot        => $mem_tot,
	};
						    
    } 
    $mem_sth->finish;
    $mem_details->finish;
    $dbh->commit;
    $kassa_list{"all"} = {
	mem_id         => "",
	name           => 'Totals',
	wh_tot         => 0,
	missing        => $all_missing,
	damaged        => $all_damaged,
	statiegeld_in  => $all_statiegeld_in,
	crates_in      => $all_crates_in, 
	misc_in        => $all_misc_in,
	statiegeld_out => $all_statiegeld_out,
	crates_out     => $all_crates_out, 
	misc_out       => $all_misc_out,
	membership     => $all_membership,
	vers_g         => $all_vers_g,
	vers_k         => $all_vers_k,
	vers_m         => $all_vers_m,
    };

    return \%kassa_list;
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
    my ($kassa_list, $config, $dbh) = @_;

    my @wh_ids;
    my @wh_names;
    my %wh_tots;
    my $h;

    my $sth = prepare("SELECT w.wh_id,  w.wh_name FROM wholesaler as w,wh_order as wo " .
		      "WHERE w.wh_id = wo.wh_id AND wo.ord_no = ?", $dbh);
    $sth->execute($config->{ord_no});
    while($h = $sth->fetchrow_hashref) {
	push @wh_ids, $h->{wh_id};
	push @wh_names, $h->{wh_name};
    }
    $sth->finish;
    $dbh->commit;

    # get all the individual wholesaler total ex-btw, total btw, grand total
    $sth = prepare("SELECT sum(f.tot) AS wh_exbtw, sum(f.tot * f.btw) AS wh_btw,  ".
		   "sum(f.tot *(100.0 + f.btw)) as wh_tot " .
		   "FROM (SELECT ".
		   "sum(whl_rcv * whl_price) AS tot, whl_btw AS btw ".
		   "FROM wh_line WHERE ord_no = ? AND wh_id = ? GROUP BY ".
		   "whl_btw) as f", $dbh);

    # get totals from mem_lines
    my $mem_sth = prepare("SELECT sum(exbtw) AS mem_exbtw, sum(btw) AS mem_btw, sum(tot) AS mem_tot, " .
			  "CAST(sum(wh_missing)/ 100 AS INTEGER) AS missing, " .
			  "CAST(sum(wh_damaged)/100 AS INTEGER) AS damaged FROM " .
			  "(SELECT (m.meml_pickup * m.meml_ex_btw) AS exbtw, " .
			  "(m.meml_pickup * meml_ex_btw * m.meml_btw) AS btw, " .
			  "(m.meml_pickup * m.meml_ex_btw * (100.0 + m.meml_btw)) AS tot, " .
			  "(m.meml_missing * p.pr_wh_price * (100 + p.pr_btw)/p.pr_wh_q) " .
			  "AS wh_missing, (m.meml_damaged * p.pr_wh_price * (100 + p.pr_btw)/p.pr_wh_q) " .
			  "AS wh_damaged FROM product as p, mem_line as m  WHERE p.pr_id = m.pr_id " .
			  "AND  m.ord_no = ? AND p.pr_wh = ?) AS wh", $dbh);

    while(my $wh = shift @wh_ids) {
	$sth->execute($config->{ord_no}, $wh);
	$h = $sth->fetchrow_hashref;
	$h->{statiegeld_in} = $h->{crates_in} = $h->{misc_in} =
	    $h->{statiegeld_out} = $h->{crates_out} = $h->{misc_out} =
	    $h->{membership} = $h->{vers_g} = $h->{vers_k} = $h->{vers_m} =
	    $h->{mem_exbtw} = $h->{mem_btw} = $h->{mem_tot} = 0;
	$h->{mem_id} = "";
	$h->{name} = shift @wh_names;
	$h->{wh_btw} = int(($h->{wh_btw} + 50) / 100);
	$h->{wh_tot} = int(($h->{wh_tot} + 50) / 100);
	$mem_sth->execute($config->{ord_no}, $wh);
	my $mh = $mem_sth->fetchrow_hashref;
	if(defined($mh)) {
	    $h->{missing}  -= $mh->{missing};
	    $h->{damaged}  -= $mh->{damaged};
	    $h->{mem_exbtw} = $mh->{mem_exbtw};
	    $h->{mem_btw}   = int($mh->{mem_btw} + 50)/100;
	    $h->{mem_tot}   = int($mh->{mem_tot} + 50)/100;
	}
	$wh_tots{$wh} = $h;
	$kassa_list->{all}->{wh_exbtw} += $h->{wh_exbtw};
	$kassa_list->{all}->{wh_btw}   += $h->{wh_btw};
	$kassa_list->{all}->{wh_tot}   += $h->{wh_tot};
	$kassa_list->{all}->{mem_exbtw} += $h->{mem_exbtw};
	$kassa_list->{all}->{mem_btw}   += $h->{mem_btw};
	$kassa_list->{all}->{mem_tot}   += $h->{mem_tot};
    }
    $mem_sth->finish;
    $sth->finish;
    $dbh->commit;
    dump_stuff("wh_tots", "", "", \%wh_tots);
    $kassa_list->{wholesalers} = \%wh_tots;
    dump_stuff("kassa_list", "", "", $kassa_list);
    return $kassa_list;
}

sub print_html_kassa_list{
    my ($config, $dbh) = @_;

    my $value;

    my $kassa = get_kassa_list_data($config, $dbh);
    $kassa = get_wholesale_data($kassa, $config, $dbh);
	
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

    # set up csv files
    my $fname_dp = "/kassa/kassalist-${order_name}_dp.csv";
    my $fname_com = "/kassa/kassalist-${order_name}_com.csv";
    open(my $fh, "> ../data$fname_dp") or die "Can't open kassalist file $fname_dp: $!";
    open(my $fh_com, "> ../data$fname_com") or die "Can't open kassalist file $fname_com: $!";

    # output header row to csv file
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

    # now the member lines to both the csv files and the browser
    foreach my $key (sort {lc($a) cmp lc($b)} (keys (%{$kassa->{mems}}))) {
        $value = $kassa->{mems}->{$key};
	foreach my $f (qw(wh_exbtw wh_btw wh_tot missing damaged statiegeld_in
			  statiegeld_out crates_in crates_out misc_in misc_out membership
                          vers_g vers_k vers_m  mem_exbtw mem_btw mem_tot)) {
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
	   
	foreach my $f (qw(wh_exbtw wh_btw wh_tot missing damaged statiegeld 
			  crates misc mem_exbtw mem_btw mem_tot)) {
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

    # now do the wholesalers
    my $first_wh = 1;
    foreach my $key (sort (keys %{$kassa->{wholesalers}})) {
        $value = $kassa->{wholesalers}->{$key};
	foreach my $f (qw(wh_exbtw wh_btw wh_tot missing damaged statiegeld_in
			  statiegeld_out crates_in crates_out
			  misc_in misc_out membership  vers_g vers_k vers_m mem_exbtw mem_btw mem_tot)) {
	    $value->{$f} = sprintf("%.2f", $value->{$f}/100.0);
	}
	print $fh "\n" if $first_wh;
	print $fh_com "\n" if $first_wh;
	my $tplw = new CGI::FastTemplate($config->{templates});
	$tplw->strict();
        $tplw->define(row => "kassalist/csv_mem_row.template", );
        $tplw->assign($value);
        $tplw->parse(MAIN => "row");
	$prref = $tplw->fetch("MAIN");
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
	$tplw = new CGI::FastTemplate($config->{templates});
	$tplw->strict();
	$tplw->define(
	    total => "kassalist/totals_row.template", 
	    row   => "kassalist/mem_row.template", 
	    );
	$tplw->assign($value);
	$tplw->parse(ROW  => "row");
	$tplw->parse(MAIN => "total");
	if($first_wh) {
	    $tplw->print("MAIN");
	    $first_wh = 0;
	} else {
	    $tplw->print("ROW");
	}
    }

    $value = $kassa->{all};
    foreach my $f (qw(wh_exbtw wh_btw wh_tot missing damaged statiegeld_in statiegeld_out 
		      crates_in crates_out misc_in misc_out membership vers_g vers_k vers_m 
                      mem_exbtw mem_btw mem_tot)) {
	$value->{$f} = sprintf("%.2f", $value->{$f}/100.0);
    }
    print $fh "\n";
    print $fh_com "\n";

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
