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
my $status;
my $err_msgs = "";
my %categories;
my %cat_descs;
my %sc_descs;

sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    my %update;
    my $vals = $cgi->Vars;
    my ($state, $mem_no, $amount, $bestel);

    return \%update if(not defined($vals->{paste}));

    # check the content:
    my @data = split("\n", $vals->{paste});
    my $line_no = 0;
    $state = 0;
    $bestel = 0;
    foreach my $l (@data) {
	++$line_no;
	$l =~ s/\s+$//;
	next if($l =~ /^$/);
	if($state == 0) {
	    # do the bestelling line
	    $state = 1;
	    if($l !~ /.*[^0-9,.-]([0-9,.-]+)\s+Bestelling$/) {
		$err_msgs .= sprintf "Row %d does not end with a price and the word Bestelling - update rejected\n", $line_no;
		return {};
	    }

	    my $bestel = $1;
	    $bestel =~ s/,/./;

	    $bestel = int(100 * $bestel);
	    if($l !~ /^(\d+)/) {
		$state = 2;
		$err_msgs .= sprintf "Row %d does not begin with a member number, this row not processed\n", $line_no;
		next;
	    }
	    $mem_no = $1;
	    $update{$mem_no} = $bestel;
	    next;
	}
	
	# do the afgewogen line
	if($l !~ /.*[^0-9,.-]([0-9.,-]+)\s+Afgewogen$/) {
	    $err_msgs .= sprintf "Row %d does not end with a price and the word Afgewogen - update rejected\n", $line_no;
		return {};
	    }
	# do nothing if we're skipping this line
	if($state == 2) {
	    $state = 0;
	    next;
	}
	$state = 0;
	$amount = $1;
	$amount =~ s/,/./;
	$amount = int(100 * $amount);
	# use bestelling amount if the final amount has not been set yet

	$update{$mem_no} = $amount if($amount != 0);
    }
    if($state != 0) {
	$err_msgs .= sprintf "Missing the Afgewogen line at end of data row %d\n", $line_no;
    }

    # got member numbers and amounts - check that the member exists. If so, if member has checked out
    # insist that the update value is the same as the vers value on the invoice
    # if member is valid, but does not have an order, create one now
    my $sth = prepare("SELECT  mem_active FROM members WHERE mem_id = ?", $dbh);
    my $mo_sth = prepare("SELECT mo_checked_out, mo_vers FROM mem_order WHERE mem_id = ? and ord_no = ?", 
			 $dbh);
    my $new_mo = prepare("SELECT open_mem_ord(?, 'f', '')", $dbh);
    my $upd_vers = prepare("UPDATE mem_order SET mo_vers = ? WHERE mem_id = ? AND ord_no = ?", $dbh);
    foreach my $mem (keys %update) {
	$sth->execute($mem);
	my $h = $sth->fetchrow_hashref;
	if(not defined($h)) {
	    $err_msgs .= sprintf "There is no member with member number %d - update rejected\n", $mem;
	    return {};
	}
	if(not $h->{mem_active}) {
	    $err_msgs .= sprintf "Member with member number %d is not active - update rejected\n", $mem;
	    return {};
	}
	$mo_sth->execute($mem, $ord_no);
	my $href = $mo_sth->fetchrow_hashref;
	if(defined($href)) {
	    # ensure that we aren't changing the amount of a checked-out member
	    if($update{$mem} != $href->{mo_vers} and $href->{mo_checked_out}) {
		$err_msgs .= sprintf "Can't change the amount for member %d who has already checked out\n",
		$mem;
		next;
	    }
	} else {
	    # create order header for member who only bought vers items
	    $new_mo->execute($mem);
	}
	$upd_vers->execute($update{$mem},  $mem, $ord_no);
	$dbh->commit;
    }
    return \%update;
}
						
sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $vars = $cgi->Vars;
    my $data = get_vars($config, $cgi, $dbh);		
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "common/adm-banner.template",
	);
    my %h =(  Pagename    => 'Upload data from Vers group spreadsheet',
	      Title       => 'Upload data from Vers group spreadsheet',
	      Nextcgi     => '/cgi-bin/vers_upload.cgi',
	      mem_name    => $config->{mem_name},
	);

    $h{BUTTONS}  = "";
    $tpl->assign(\%h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print "$err_msgs<p/>" if(length($err_msgs) > 0); 

    my $tpb = new CGI::FastTemplate($config->{templates});
    $tpb->strict();
    $tpb->define( body      => "vers_upload/vers_paste_buf.template");
    $tpb->assign({});
    $tpb->parse(MAIN => "body");
    $tpb->print("MAIN");
    $dbh->disconnect;
    exit 0;

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

    if($program =~ /login/) {
	$mem_id = process_login(1, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(1, $config, $cgi, $dbh);
    }
    $config->{mem_id} = $mem_id;
    my $sth = prepare('SELECT ord_no, ord_status FROM order_header', $dbh);
    $sth->execute;
    my $aref = $sth->fetchrow_arrayref;
    if(not defined($aref)) {
	die "Could not get order no and status";
    }
    $sth->finish;

    ($ord_no, $status) = @{$aref};
    $config->{check_out} = 0;
    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
