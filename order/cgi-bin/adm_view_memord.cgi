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
use view_member;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $current_no;
my $status;
my $err_msgs = "";
my $config;

sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    my %pr_dat;
    my $vals = $cgi->Vars;
    my %new_vals;
    my %buttons;

    $config->{showbtw} = (defined($vals) and (defined($vals->{showbtw}))); 
    $config->{showall} = (defined($vals) and (defined($vals->{showall}))); 
    $config->{showbtw} = 0 if($config->{showall});

    if(not defined($vals) or not defined($vals->{order_no})) {
	# first entry, no selector, default is current order
	($config->{labels}, $config->{selector}) = 
	    order_selector($ord_no, $ord_no, $dbh);
	return (\%new_vals, \%buttons) if(not defined($vals));
    }

    if(defined($vals->{order_no})) {
	# we want a specific order
	$ord_no = $vals->{order_no};
	($config->{labels}, $config->{selector}) = 
	    order_selector($current_no, $ord_no, $dbh);
	$status = 7 if($ord_no != $current_no);
    }

    # copy the buttons 
    foreach my $but ( qw( IncOrd Member )) {
	if (defined($vals->{$but})) {
	    $buttons{$but} = $vals->{$but};
	}
    }

    return (\%new_vals, \%buttons);
}


sub print_html {
    my ($config, $cgi, $dbh) = @_;
    
    my $mem_stuff = escapeHTML( "$mem_id ($config->{fullname})" );

    if ( $status < 3 ) {
	$config->{title} = ( $config->{committed} )
	    ? "View Committed Order for Member $mem_stuff"
	    : "View Uncommitted Order for Member $mem_stuff";
    } else {
	$config->{title} = 
	    "View $config->{labels}->{$ord_no} Order for Member $mem_stuff";
    }
	
    $config->{buttons}  = "adm_view_memord/adm_member_buttons.template";
    $config->{nextcgi}  = "adm_view_memord.cgi";

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  prbuttons   => $config->{buttons});
    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => $config->{nextcgi},
		  IncOrdTxt   => "Show only items in my order",
		  mem_name    => $config->{mem_name},
		  mem_id      => $mem_id,
		  btwchecked  => (($config->{showbtw}) ? 
		  "CHECKED" : ""),
		  allchecked  => (($config->{showall}) ? 
		  "CHECKED" : ""),
	);


    $hdr_h{DROP} = ($config->{all}) ? "&nbsp" : $config->{selector};
    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "prbuttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "<p class = \"warn\">$err_msgs<p/>" if(length($err_msgs) > 0); 
    $config->{status} = $status;
    $config->{ord_no} = $ord_no;
    $config->{mem_id} = $mem_id;
    display_mem_order($config, $cgi, $dbh);
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    print_html($config, $cgi, $dbh);
}

# get member no, has_order, member_name 
sub mem_id_and_status {
    my ($val, $dbh) = @_;
    my @res = (undef, 0, undef);

    my $cmd;
    $val =~ s/^\s*//;
    $val =~ s/^\s$//;
    return (undef, 0, undef) if($val eq "");
    if($val !~ /\@/) {
	$val = int($val);
	return(@res) if($val <= 0);
	$cmd = "mem_id = ?";
    } else {
	$cmd = "mem_email ilike ?";
    }
    $cmd = "SELECT mem_id, join_name(mem_fname, mem_prefix, mem_lname) FROM " .
	"members WHERE $cmd";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($val);
    my $a = $sth->fetchrow_arrayref;
    return(@res) if(not defined($a));
    $res[0] = $a->[0];
    $res[2] = $a->[1];
    $cmd = "SELECT o.memo_commit_closed IS NOT NULL  FROM members AS m, ".
	"mem_order AS o WHERE m.mem_id = o.mem_id AND o.ord_no = ? ".
	"AND m.mem_id = ?";
    $sth = prepare($cmd, $dbh);
    $sth->execute($ord_no, $res[0]);
    $a = $sth->fetchrow_arrayref;
    $sth->finish;
    $res[1] = ((defined($a)) and $a->[0]);
    return(@res);
}

sub get_mem_no {
    my ($cgi, $dbh) = @_;

    $dbh->disconnect;
    my %h = (Pagename => 'Select Member Order to View',
	     mem_name    => $config->{mem_name},
	     Title    => 'Select Member Order to View');
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "adm_view_memord/adm_select_member.template",
		  banner      => "common/adm-banner.template",
	);
    $h{BUTTONS} = "";
    $tpl->assign(\%h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    exit 0;
}

sub main {
	
    my $program	= $0;
    $program	=~ s/.*\///;

    syslog(LOG_ERR, "$program");
    $config = read_conf($conf);
    openlog( $program, LOG_PID, LOG_USER );

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if ( $program =~ /mem-login/ ) {
	process_login(1, $cgi, $dbh);
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }
	
    $current_no = $ord_no;
    my ($junk, $buttons) = get_vars($config, $cgi, $dbh);
    
    if ( !defined($buttons->{Member} )  or $buttons->{Member} eq "") {
	get_mem_no($cgi, $dbh);  # never returns
    } else {
	($mem_id, $config->{committed}, $config->{fullname}) = 
	    mem_id_and_status($buttons->{Member}, $dbh);
	get_mem_no($cgi, $dbh) if(not defined($mem_id));
    }

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}

main;
