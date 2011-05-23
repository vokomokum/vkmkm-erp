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

# get variables from pasted spread-sheet
# inputs give type (groente/kaas/misc) and paste - the text from the spread sheet
# output is a hash with key = mem_id, values amount and an ordingal for the spreadsheet 
# row , then a string identifying if it's groente, kaas or misc(ellaneous)
sub get_ss_vars {
    my ($config, $cgi, $dbh) = @_;
    my %update;
    my $vals = $cgi->Vars;
    my ($state, $mem_no, $amount, $bestel);
    my $which = "";
    my $count = 0;
    $which = 'groente' if(defined($vals->{Groente}));
    $which = 'kaas' if(defined($vals->{Kaas}));
    $which = 'misc' if(defined($vals->{"Misc."}));

    return (\%update, $which) if(not defined($vals->{paste}) or $which eq "");

    # check the content:
    my @data = split("\n", $vals->{paste});
    my $line_no = 0;
    $state = 0;
    $bestel = 0;
    foreach my $l (@data) {
	++$line_no;
	$l =~ s/\s+$//;	next if($l =~ /^$/);
	next if($l !~ /\s+afgewogen/i);
	if($l !~ /^(\d+)/) {
	    $err_msgs = err_msg_2_html((sprintf
					"Row %d does not begin with a member number, this row not processed\n",
					$line_no), $err_msgs, $config);
	    next;
	}
	$mem_no = $1;
		
	# do the afgewogen line
	if($l !~ /.*[^0-9,.-]([0-9.,-]+)\s+Afgewogen$/i) {
	    $err_msgs = err_msg_2_html((sprintf 
		"Row %d does not end with a price and the word Afgewogen - update rejected\n", 
				       $line_no), $err_msgs, $config);
	    return ({}, "");
	}

	$amount = $1;
	$amount =~ s/,/./;
	$amount = int(100 * $amount);
	if(not defined($update{$mem_no})) {
	    $update{$mem_no}->{amt} = $amount;
	    # remember the spreadshhet ordering of rows
	    $update{$mem_no}->{ordinal} = $count++;
	} else {
	    $update{$mem_no}->{amt} += $amount;
	}
    }
    if($state != 0) {
	$err_msgs = err_msg_2_html((sprintf "Missing the Afgewogen line at end of data row %d\n", 
				    $line_no), $err_msgs, $config);
    }

    # got member numbers and amounts - check that the member exists. 
    my $sth = prepare("SELECT  mem_active, join_name(mem_fname, mem_prefix, mem_lname) ".
		      "AS fullname FROM members WHERE mem_id = ?", $dbh);
    foreach my $mem (keys %update) {
	$sth->execute($mem);
	my $h = $sth->fetchrow_hashref;
	if(not defined($h)) {
	    $err_msgs = err_msg_2_html((sprintf "There is no member with member number %d - ". 
					"update rejected\n", $mem), $err_msgs, $config);
	    return ({}, $which);
	}
	if(not $h->{mem_active}) {
	    $err_msgs = err_msg_2_html((sprintf "Member with member number %d is not active " .
					"- update rejected\n", $mem), $err_msgs, $config);
	    return ({}, $which);
	}
	$update{$mem}->{name} = $h->{fullname};
	$update{$mem}->{old_amt}  = 0;
    }
    return (\%update, $which);
}

# get the spreadsheet and the type. fetch values from db to match with spreadsheet
						
sub doit_ss {
    my ($config, $cgi, $dbh) = @_;
    my $vars = $cgi->Vars;

    my ($data, $which)  = get_ss_vars($config, $cgi, $dbh);		

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "common/adm-banner.template",
		  buttons     => "vers_upload/vers_upload_buttons.template",
	);
    my %h =(  Pagename    => 'Upload data from Vers group spreadsheet',
	      Title       => 'Upload data from Vers group spreadsheet',
	      Nextcgi     => '/cgi-bin/vers_upload.cgi',
	      mem_name    => $config->{mem_name},
	);

    $h{BUTTONS} = "" if($which eq "" or scalar(keys(%{$data})) == 0);
	
    $tpl->assign(\%h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(BUTTONS => "buttons") if($which ne "" and scalar(keys(%{$data})) != 0);

    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    # output starting page until we have some data and a vers group type
    if($which eq "" or scalar(keys(%{$data})) == 0) {
	$dbh->commit;
	$dbh->disconnect;

	if(length($err_msgs) > 0) {
	    print "$err_msgs<p/>" 
	}
	my $tpb = new CGI::FastTemplate($config->{templates});
	$tpb->strict();
	$tpb->define( body      => "vers_upload/vers_paste_buf.template");
	$tpb->assign({});
	$tpb->parse(MAIN => "body");
	$tpb->print("MAIN");
	exit 0;
    }

    # we have some data to work with
    my $column = "mo_vers_$which";
    my $ordinal = scalar(keys(%{$data}));
    my $sth = prepare("SELECT l.mem_id, $column, l.mo_checked_out, " . 
		      "join_name(m.mem_fname, m.mem_prefix, m.mem_lname) AS fullname " .
		      "FROM mem_order AS l, members as m " .
		      "WHERE ord_no = ? AND l.mem_id = m.mem_id", $dbh);
    $sth->execute($config->{ord_no});
    while(my $h = $sth->fetchrow_hashref) {
	if(!defined($data->{$h->{mem_id}})) {
	    # skip members with zero amounts not in spreadsheet
	    next if($h->{$column}) == 0;
	    # member has an amount for this vers type, but isn't in spreadsheet
	    $data->{$h->{mem_id}} = {ordinal => $ordinal++,
				     amt => $h->{$column}};
	} elsif($h->{mo_checked_out}) {
	    if ($h->{$column} != $data->{$h->{mem_id}}->{amt}) {
		$err_msgs = err_msg_2_html("Can't change amount for member $h->{mem_id} " .
					   "because the order is checked out<br>", $err_msgs, $config);
	    }
	    $data->{$h->{mem_id}}->{noedit} = 1;
	}
	$data->{$h->{mem_id}}->{old_amt} = $h->{$column};
	$data->{$h->{mem_id}}->{name} = $h->{fullname};
    }

    $sth->finish;
    $dbh->commit;
    $dbh->disconnect;

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 

    my $tpr = new CGI::FastTemplate($config->{templates});
    $tpr->strict();
    $tpr->define(body   => "vers_upload/vers_upload_table.template",
	         row    => "vers_upload/vers_upload_row.template",
		 noedit => "vers_upload/vers_upload_noedit.template",
	);

    for my $mem_id (sort{$data->{$a}->{ordinal} <=> $data->{$b}->{ordinal}}  
		    (keys %{$data})) {
	my $h = $data->{$mem_id};
	$h->{mem_id} = $mem_id;
	$h->{colour} = ($h->{old_amt} == $h->{amt}) ? "myorder" : "editok";
	$h->{ident}  = "${column}_$mem_id";
	$h->{new}    = sprintf "%0.2f", $h->{amt}/100.0;
	$h->{old}    = sprintf "%0.2f", $h->{old_amt} / 100.0;
	$h->{mem_name} = escapeHTML($h->{name});
	$tpr->assign($h);

	if(defined($h->{noedit})) {
	    $tpr->parse(ROWS => ".noedit");
	} else {
	    $tpr->parse(ROWS => ".row");
	}
	$tpr->clear_href(1);
    }
    $tpr->assign( {Title => "Vers groep $which", which => $which, column=>$column});
    $tpr->parse(MAIN => "body");
    $tpr->print("MAIN");
    exit 0;
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $vars = $cgi->Vars;

    if(!defined($vars->{column}) or !defined($vars->{which}) or defined($vars->{Cancel})) {
	doit_ss($config, $cgi, $dbh);
	exit 0;
    }
    my $column = $vars->{column};
    my $which  = $vars->{which};
    my $sel_sth = prepare("SELECT count(*) AS n FROM mem_order  WHERE mem_id = ? and ord_no = ?",
			  $dbh);
    my $upd_sth = prepare("UPDATE mem_order SET $column = ? WHERE mem_id = ? and ord_no = ?", $dbh);
    my $new_sth = prepare("SELECT open_mem_ord(?, 'f', '')", $dbh);

    
    for my $k (keys %{$vars}) {
	next if($k !~ /^(.*)_(\d+)$/);
	next if($1 ne $column);
	my $mem = $2;
	$sel_sth->execute($mem, $config->{ord_no});
	my $h = $sel_sth->fetchrow_hashref;
	if($h->{n} == 0) {
	    $new_sth->execute($mem);
	    $dbh->commit;
	}
	$upd_sth->execute(int(100 * $vars->{$k}), $mem, $config->{ord_no});
	$dbh->commit;
    }
    $sel_sth->finish;
    $upd_sth->finish;
    $new_sth->finish;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "common/adm-banner.template",
		  buttons     => "vers_upload/vers_upload_buttons.template",
	);
    my %h =(  Pagename    => 'Upload data from Vers group spreadsheet',
	      Title       => 'Upload data from Vers group spreadsheet',
	      Nextcgi     => '/cgi-bin/vers_upload.cgi',
	      mem_name    => $config->{mem_name},
	);

    $tpl->assign(\%h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(BUTTONS => "buttons");

    $tpl->parse(BANNER => "banner");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    my $data = {};

    my $ordinal = 0;
    my $sth = prepare("SELECT l.mem_id, $column, l.mo_checked_out, " . 
		      "join_name(m.mem_fname, m.mem_prefix, m.mem_lname) AS fullname " .
		      "FROM mem_order AS l, members as m " .
		      "WHERE ord_no = ? AND l.mem_id = m.mem_id", $dbh);
    $sth->execute($config->{ord_no});
    while(my $h = $sth->fetchrow_hashref) {
	$data->{$h->{mem_id}} = {ordinal => $ordinal++,
				 amt     => $h->{$column},
				 old_amt => $h->{$column},
				 name    => $h->{fullname},
	};
	$data->{$h->{mem_id}}->{noedit} = 1 if($h->{mo_checked_out});
    }

    $sth->finish;
    $dbh->commit;
    $dbh->disconnect;

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 

    my $tpr = new CGI::FastTemplate($config->{templates});
    $tpr->strict();
    $tpr->define(body   => "vers_upload/vers_upload_table.template",
	         row    => "vers_upload/vers_upload_row.template",
		 noedit => "vers_upload/vers_upload_noedit.template",
	);

    for my $mem_id (sort{lc($data->{$a}->{name}) cmp lc($data->{$b}->{name})}  
		    (keys %{$data})) {
	next if(!defined($vars->{"${column}_$mem_id"}) and $data->{$mem_id}->{amt} == 0 and
		$data->{$mem_id}->{old_amt} == 0);
	my $h = $data->{$mem_id};
	$h->{mem_id} = $mem_id;
	$h->{colour} = ($h->{old_amt} == $h->{amt}) ? "myorder" : "editok";
	$h->{ident}  = "${column}_$mem_id";
	$h->{new}    = sprintf "%0.2f", $h->{amt}/100.0;
	$h->{old}    = sprintf "%0.2f", $h->{old_amt} / 100.0;
	$h->{mem_name} = escapeHTML($h->{name});
	$tpr->assign($h);

	if(defined($h->{noedit})) {
	    $tpr->parse(ROWS => ".noedit");
	} else {
	    $tpr->parse(ROWS => ".row");
	}
	$tpr->clear_href(1);
    }
    $tpr->assign( {Title => "Vers groep $which", which => $which, column=>$column});
    $tpr->parse(MAIN => "body");
    $tpr->print("MAIN");
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
