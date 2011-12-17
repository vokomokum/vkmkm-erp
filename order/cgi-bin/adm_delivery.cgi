#! /usr/bin/perl -w 

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
use voko;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $current_no;
my $cur_label;
my $status;
my $err_msgs = "";

sub get_shorts {
    my ($dbh) = @_;
    my %shorts;
    
    my $sh_st = 
      'SELECT *  FROM sh_view WHERE ord_no = ?'; 
    my $sh_sth = prepare($sh_st, $dbh);
    $sh_sth->execute($ord_no);
    while(my $a = $sh_sth->fetchrow_hashref) {
	my $pr_id = $a->{pr_id};
	$a->{cost}  = sprintf "%0.2f", $a->{cost};
	$a->{unit_pr}  = sprintf "%0.2f", $a->{unit_pr};
	$shorts{"${pr_id}_$a->{mem_id}"} = $a;
    }
    $sh_sth->finish;
    return (\%shorts);
}

# we get back the selected wholesaler key wh_name as a string which we will look up 
# in a hash. We'll display up to four wholesalers, to avoid too much use of drop-down
# menus.
# the only other input is a submit button

# return a hash of arrays [ [ wh_id, wh_name] ] sorted by wh_id
# for creating the select we just use the 2nd element from each subarray
# we'll do s strng search for the wholesaler ID 

sub get_wholesalers {
    my ($dbh) = @_;
    my %wholesalers;
    my $sth = prepare("Select wh_id, wh_name FROM wholesaler ORDER BY wh_id", $dbh);
    $sth->execute;
    while(my $aref = $sth->fetchrow_arrayref) {
	$wholesalers{$a->[0]} = $a->[1];
    }
    $sth->finish();
    return \%wholesalers;
}

# get the selection - inputs to the form will be 
# pr_<pr_id>_<qty>
sub get_vars {
    my ($config, $cgi, $dbh) = @_;

    my %whlq;
    my $vals = $cgi->Vars;

    if(not defined($vals) or not defined($vals->{order_no})) {
	# first entry, no selector, default is current order
	($config->{labels}, $config->{selector}) = 
	    order_selector($ord_no, $ord_no, $dbh);
	return (\%whlq) if(not defined($vals));
    }

    if(defined($vals->{order_no})) {
	# we want a specific order
	$ord_no = $vals->{order_no};
	($config->{labels}, $config->{selector}) = 
	    order_selector($current_no, $ord_no, $dbh);
	$status = 7 if($ord_no != $current_no);
    }

    foreach my $whl (keys %{$vals}) {
	my $q = $vals->{$whl};
	next if($whl !~ /w_(\d+)$/);
	$whl = $1;
	$q =~ s/^\s*//;
	$q =~ s/\s*$//;
	$q = '0' if($q eq "");
	$whlq{$whl} = $q;
    }

    return \%whlq;
}

# create an array of  hashrefs of items to display from $wh_view
# will have a complete wh_view line with an additional new value line

sub get_lines {
    my ($config, $cgi, $dbh) = @_;
    my @pr;
    my $whlq = get_vars($config, $cgi, $dbh);

    my $sth = prepare("SELECT * FROM wh_view_all WHERE ord_no = ?", $dbh);
    $sth->execute($ord_no);
    while(my $h = $sth->fetchrow_hashref) {
	my $pr_id = $h->{pr_id};
	$h->{newq} = (defined($whlq->{$pr_id})) ?
	    $whlq->{$pr_id} : $h->{received};
	$h->{prcode} = escapeHTML($h->{prcode});
	$h->{descr} = escapeHTML($h->{descr});
	$h->{price_inc_btw} = sprintf("%0.2f", $h->{price_inc_btw});
	push @pr, $h;
    }
    $sth->finish;
    return \@pr;
}
	    
# we've got the submitted variables. Get the current database state
# and apply any changed values
sub do_changes {
    my ($config, $cgi, $dbh) = @_;
    my $pr = get_lines($config, $cgi, $dbh);
    my $sth = prepare('SELECT enter_delivery_shortage(?, ?)', $dbh);

    while(my $h = shift @{$pr}) {
	last if($status != 5);

	next if($h->{received} == $h->{newq});

	eval {
	    $sth->execute($h->{pr_id}, $h->{newq});
	};
	if($@) {
	    my $e = $@;
	    $e =~ s/.*ERROR: *//;
	    $e =~ s/\s*$//;
	    if(length($err_msgs) == 0) {
		my $tpl = new CGI::FastTemplate($config->{templates});
		$tpl->strict();
		$tpl->define( emsg      => "adm_delivery/err_wh_title.template");
		my %em = (err_msg => $e);
		$tpl->assign(\%em);
		$tpl->parse(MAIN => "emsg");
		my $e = $tpl->fetch("MAIN");
		$err_msgs = $$e;
		$tpl = undef;
	    }
	    $dbh->rollback();
	    my $tplr = new CGI::FastTemplate($config->{templates});
	    $tplr->define(row => "adm_delivery/adm_wh_err_row.template");
	    $h->{received} = $h->{newq};
	    $tplr->assign($h);
	    $tplr->parse(MAIN => "row");
	    my $ee = $tplr->fetch("MAIN");
	    $err_msgs = $err_msgs . $$ee;
	    $tplr = undef;
	} else {
	    $dbh->commit;
	}
    }

    if($status == 5) {
	$config->{title}    = "Enter Delivery Shortages";
	$config->{row}      = "adm_delivery/adm_editwhrow.template";
    } else {
	$config->{title}   = "View $config->{labels}->{$ord_no} Wholesale Order";
	$config->{row}     = "adm_delivery/adm_noeditwhrow.template";
    }
    $config->{nextcgi}  = "/cgi-bin/adm_delivery.cgi";
}

sub print_html {
    my ($config, $cgi, $dbh) = @_;
    my $pra = get_lines($config, $cgi, $dbh);
    my $last_whn = 0;
    my $rowclass = "myorder";
    my $fh = undef;
    my $fn = "";
    my $chk_fh = undef;
    my $chk_fh_nl = undef;
    my $chk_fn = "";
    my $chk_fn_nl = "";

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "common/adm-banner.template",
		  prbuttons   => "adm_delivery/adm_save.template");
    my %h =(  Pagename    => $config->{title},
	      Title       => $config->{title},
	      Nextcgi     => $config->{nextcgi},
	      checked     => (($config->{all}) ? "" :  'CHECKED'),
	      mem_name    => $config->{mem_name},
	);

    $h{BUTTONS}  = "$config->{selector}<input type=\"Submit\" value=\"Go\" /><table class=\"main\">" 
	if ($status != 5);
    $tpl->assign(\%h);
    
    $tpl->parse(BUTTONS => "prbuttons") if($status == 5);
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print "$err_msgs<p/>" if(length($err_msgs) > 0); 
    my $total = 0;
    my $total_ref = 0;
    my $total_inc = 0;
    my $line = 0;

    foreach my $h (@{$pra}) {
	next if($status != 5 and  $h->{qty} == 0);

	if(($line %20) == 0) {
	    print_title("adm_delivery/adm_wh_titles.template", $line, 
			"Description", $config);
	}
	++$line;
	if($h->{wh_no} != $last_whn) {
	    if($last_whn != 0) {
		close($fh) if(defined($fh));
		$fh = undef;
		close($chk_fh) if(defined($chk_fh));
		$chk_fh = undef;
		close($chk_fh_nl) if(defined($chk_fh));
		$chk_fh_nl = undef;

		$tpl = new CGI::FastTemplate($config->{templates});
		$tpl->define(row  => "adm_delivery/adm_whtotals.template",
		             link => "adm_delivery/adm_wh_link.template");
		my $r = { 
		    filename  => $fn,
		    chk_filename => $chk_fn,
		    chk_filename_nl => $chk_fn_nl,
		    total     => sprintf("%.2f", $total), 
		    total_inc => sprintf("%.2f", $total_inc), 
		    total_ref => sprintf("%.2f", $total_ref),
		    RowClass  => $rowclass,
		};

		$tpl->assign($r);
		$tpl->parse(LINK => "link");

		$tpl->parse(TOTAL => "row");
		# toggle colour
		$rowclass = ($rowclass eq "editok") ? "myorder" : "editok";
		$tpl->print("TOTAL");
		$total = $total_inc = $total_ref = 0;
		print_title("adm_delivery/adm_wh_titles.template", $line, 
			    "Description", $config);
		$line = 1;
	    }
	    $last_whn = $h->{wh_no};
	    if(1) {
#	    if($h->{wh_no} == $config->{DNB}->{dnb_wh_id}) {
		my $ord_date = ($ord_no == $current_no) ?
		    $cur_label : $config->{labels}->{$ord_no};
		$fn = "/orders/WH-$h->{wh_no}-$ord_date.txt";
		$chk_fn = "/orders/Check_WH-$h->{wh_no}-$ord_date.txt";
		$chk_fn_nl = "/orders/Check_WH-$h->{wh_no}-$ord_date-NL.txt";
		open($fh, "> ../data$fn") or 
		    die "Can't open order file ../data$fn: $!";
		open($chk_fh, "> ../data$chk_fn") or 
		    die "Can't open order file ../data$chk_fn: $!";
		open($chk_fh_nl, "> ../data$chk_fn_nl") or 
		    die "Can't open order file ../data$chk_fn_nl: $!";
	    }
	}

	printf $fh "%s\t%d\r\n", (($h->{prcode} < 1000)  ?
	    (sprintf "%04.4d", $h->{prcode}) : $h->{prcode}), $h->{qty}
	    if(defined($fh) and $h->{qty} != 0);
	my $a_row = sprintf "%s\t%s\t%d\t%s\t%s\r\n", (($h->{prcode} < 1000)  ?
	    (sprintf "%04.4d", $h->{prcode}) : $h->{prcode}),
	    $h->{descr}, $h->{qty}, $h->{price},
	    $h->{price_inc_btw};	
	print $chk_fh $a_row if(defined($chk_fh) and $h->{qty} != 0);
	$a_row =~ s/\./,/g;
	print $chk_fh_nl $a_row if(defined($chk_fh) and $h->{qty} != 0);
	$total += $h->{price};
	$total_inc += $h->{price_inc_btw};
	$h->{RowClass} = $rowclass;
	$h->{Qty} = ($h->{qty} != $h->{received}) ? "qtyinpgry" : "qtyinp";

	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->define(row => $config->{row});
	$tplr->assign($h);
	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;
    }
    close($fh) if(defined($fh));
    close($chk_fh) if(defined($chk_fh));
    close($chk_fh_nl) if(defined($chk_fh_nl));
    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define(row  => "adm_delivery/adm_whtotals.template",
		 link => "adm_delivery/adm_wh_link.template");
    my $r = { 
	filename  => $fn,
	chk_filename => $chk_fn,
	chk_filename_nl => $chk_fn_nl,
	total     => sprintf("%.2f", $total), 
	total_inc => sprintf("%.2f", $total_inc), 
	total_ref => sprintf("%.2f", $total_ref),
	RowClass  => $rowclass,
    };
    $tpl->assign($r);
    if(defined($fh)) {
	$tpl->parse(LINK => "link");
    } else {
	$r->{LINK} = "";
    }

    $tpl->parse(TOTAL => "row");
    $tpl->print("TOTAL");
    print <<EOF
</table>
</form>
</body>
</html>
EOF
;
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    do_changes($config, $cgi, $dbh);
    print_html($config, $cgi, $dbh);
}
    

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
    ($status, $ord_no, $cur_label) = ($config->{status}, $config->{ord_no},
				      $config->{ord_label});

    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    $current_no = $ord_no;
    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
