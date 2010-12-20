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

my $conf = "/var/www/voko/passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
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
# pr_<pr_id>_<qty>w-
sub get_vars {
    my ($config, $cgi) = @_;

    my %whlq;
    my $vals = $cgi->Vars;

    return (\%whlq) if(not defined($vals));

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
    my $whlq = get_vars($config, $cgi);

    my $sth = prepare("SELECT * FROM wh_view ORDER BY wh_no, pr_id", $dbh);
    $sth->execute;
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
	last if($status != 6);
	next if($h->{receved} == $h->{newq});
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
		$tpl->define( emsg      => "./err_wh_title.template");
		my %em = (err_msg => $e);
		$tpl->assign(\%em);
		$tpl->parse(MAIN => "emsg");
		$err_msgs =  ${$tpl->fetch("MAIN")};
		$tpl = undef;
	    }
	    $dbh->rollback();
	    my $tplr = new CGI::FastTemplate($config->{templates});
	    $tplr->define(row => "./adm_wh_err_row.template");
	    $h->{received} = $h->{newq};
	    $tplr->assign($h);
	    $tplr->parse(MAIN => "row");
	    $err_msgs = $err_msgs . ${$tplr->fetch("MAIN")};
	    $tplr = undef;
	} else {
	    $dbh->commit;
	}
    }

    if($status == 5) {
	$config->{title}    = "Enter Delivery Shortages";
	$config->{row}      = "./adm_editwhrow.template";
    } else {
	$config->{title}   = "View Wholesale Order";
	$config->{row}     = "./adm_noeditwhrow.template";
    }
    $config->{nextcgi}  = "/cgi-bin/adm_delivery.cgi";
}

sub print_html {
    my ($config, $cgi, $dbh) = @_;
    my $pra = get_lines($config, $cgi, $dbh);
    my $last_whn = 0;
    my $rowclass = "editok";

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "header.template",
		  banner      => "adm-banner.template",
		  prbuttons   => "adm_save.template");
    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => $config->{nextcgi},
		  IncOrdTxt   => "Show only items in my order",
		  checked     => (($config->{all}) ? "" :  'CHECKED'),
		  mem_name    => $config->{mem_name},
	);


    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "prbuttons");
    admin_banner($status, "BANNER", "banner", $tpl);
    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 
    my $total = 0;
    my $line = 0;

    foreach my $h (@{$pra}) {

	if(($line %20) == 0) {
	    print_title("./adm_wh_titles.template", $line, "Description", $config);
	}
	++$line;
	# toggle colour
	if($h->{wh_no} != $last_whn) {
	    $last_whn = $h->{wh_no};
	    $rowclass = ($rowclass eq "editok") ? "myorder" : "editok";
	}
	$h->{RowClass} = $rowclass;
	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->define(row => $config->{row});
	$tplr->assign($h);
	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;
    }
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

    # verify config is complete
    my @must_have = qw(dbase_name dbase_server);
    my @get_prod_must_have = qw(dbase_user dbase_password);

    foreach my $mh ( @must_have ) {
	die "Missing config file general entry $mh" 
	    if( not defined( $config->{$mh}));
    }
    foreach my $mh ( @get_prod_must_have ) {
	die "Missing config file general entry $mh" 
	    if( not defined( $config->{get_prod}->{$mh} ) );
    }

    my $cgi = new CGI;
    my $dbh = connect_database($config);
    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    my $sth = prepare('SELECT ord_no, ord_status FROM order_header', $dbh);
    $sth->execute;
    my $aref = $sth->fetchrow_arrayref;
    if(not defined($aref)) {
	die "Could not get order no and status";
    }
    $sth->finish;

    ($ord_no, $status) = @{$aref};

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
