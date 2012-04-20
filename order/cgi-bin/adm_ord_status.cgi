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

my %status_descrs = (
    0 => "Begin New Order cycle", 
    1 => "Order is open for members",
    2 => "Members can only place orders which do not increase shortages",
    3 => "Orders are closed, admins must adjust member orders to resolve shortages",
    4 => "All changes are complete, the order is ready for sending to the wholesalers",
    5 => "The order has been received, admins must enter any delivery shortages",
    6 => "Admins must adjust member orders to resolve  delivery shortages",
    7 => "The order is finished, member invoices can be prepared",
    );

# new order cycle - do it if we have a name
sub set_status_0 {
    my ($vars, $config, $cgi, $dbh) = @_;

    if($status != 7) {
	$err_msgs = "There is still an order open [$config->{current_ord}]";
	return;
    }
    if(!defined($vars->{ord_name}) or $vars->{ord_name} eq '') {
	$err_msgs = "Please enter a name for this order";
	return;
    }
    $config->{order_name} = $vars->{ord_name};
    eval {
	my $sth = prepare('SELECT set_status_0(?)', $dbh);
	$sth->execute($vars->{ord_name});
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
    $dbh->commit;

}

# same as status 0, as we no longer deal with commits
sub set_status_1 {
    my ($vars, $config, $cgi, $dbh) = @_;
    if($status  > 1) {
	$err_msgs = "Commits are already allowed";
	return;
    }
    eval {
	my $sth = prepare('SELECT set_status_1()', $dbh);
	$sth->execute;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
    $dbh->commit;
    
}

# member shortage adjust time - allow updates
sub set_status_2 {
    my ($vars, $config, $cgi, $dbh) = @_;

    my $sth;
    my $aref;

    if(not defined($vars->{Close})) {
	$config->{button} = "Close";
	$config->{reminders} = 1;
	return; 
    }

    eval {
	$sth = prepare('SELECT set_status_2(?)', $dbh);
	$sth->execute('t');
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
        $dbh->rollback;
        return;
    }
    if($aref->[0] != 0) {
	$err_msgs = "Could not close commits, please try again";
	$dbh->rollback;
    }
    $dbh->commit;

}

# close member order activity
sub set_status_3 {
    my ($vars, $config, $cgi, $dbh) = @_;

    eval {
	my $sth = prepare('SELECT set_status_3()', $dbh);
	$sth->execute;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
    $dbh->commit;
    
}

# close order adjustment phase, requires adjustments to be finished
sub set_status_4 {
    my ($vars, $config, $cgi, $dbh) = @_;
    my $sth;
    my $aref;

    eval {
	$sth = prepare('SELECT set_status_4()', $dbh);
	$sth->execute();
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
    $dbh->commit;
    if($aref->[0] != 0) {
	$err_msgs = "There are still $aref->[0] order shortages to be resolved";
	return;
    }
}

# start delivery adjustment phase
sub set_status_5 {
    my ($vars, $config, $cgi, $dbh) = @_;

    eval {
	my $sth = prepare('SELECT set_status_5()', $dbh);
	$sth->execute;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
    $dbh->commit;
}

# delivery shortages entered, start adjusting member orders

# close delivery shortage entry phase
sub set_status_6 {
    my ($vars, $config, $cgi, $dbh) = @_;
    my $sth;
    my $aref;

    if(not defined($vars->{Close})) {
	$err_msgs = "Please confirm that all delivery shortages have been entered";
	$config->{text} = "All delivery shortages have been entered";
	$config->{button} = "Close";
	return;
    }
    eval {
	$sth = prepare('SELECT set_status_6()', $dbh);
	$sth->execute();
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
	$dbh->commit;

}

# close order, requires adjustments to be finished
sub set_status_7 {
    my ($vars, $config, $cgi, $dbh) = @_;
    my $sth;
    my $aref;

    eval {
	$sth = prepare('SELECT set_status_7()', $dbh);
	$sth->execute();
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
    };
    if($dbh->err) {
	$err_msgs = $dbh->errstr;
	$dbh->rollback;
	return;
    }
	$dbh->commit;
    if($aref->[0] != 0) {
	$err_msgs = "There are still $aref->[0] order shortages to be resolved";
	return;
    }
}



sub print_html {
    my ($config, $cgi, $dbh) = @_;

    my @members;
    if ($status == 1 or $status == 2) {
	my $sth = prepare("SELECT * FROM unc_email ORDER BY mem_id", $dbh);
	$sth->execute;
	while(my $h = $sth->fetchrow_hashref) {
	    $h->{fullname} = escapeHTML($h->{fullname});
	    $h->{mem_email} = escapeHTML($h->{mem_email});
	    push @members, $h;
	    $config->{reminder} = 1;
	}
	
	$sth->finish;
    }

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $config->{title} = "Change Order Status";
    $tpl->define( page        => "common/status_header.template",
	          header      => "common/header.template",
		  banner      => "common/adm-banner.template",
  		  status_chg  => "adm_ord_status/order_status.template",
		  ord_name    => "adm_ord_status/order_name.template",
		  send_rem    => "adm_ord_status/send_com_rem.template", 
	);
    my %h =(      Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => "/cgi-bin/adm_ord_status.cgi",
		  mem_name    => $config->{mem_name},
		  cur_status  => $status_descrs{$status},
		  new_status  => $status_descrs{($status + 1)%8},
		  text        => $config->{text},
		  err_msgs    => $err_msgs,
		  conf_button => $config->{button},
		  order_name  => escapeHTML($config->{order_name}),
		  BUTTONS     => ""
	);

    $tpl->assign(\%h);
    if($status == 7) {
	$tpl->parse(NAME => "ord_name");
    } elsif($config->{reminder}) {
	$tpl->parse(NAME => "send_rem");
    } else {
	$h{NAME} = "";
    }

    $tpl->parse(BODY => "status_chg"); 
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(HEADER => "header");
    $tpl->parse(MAIN => "page");
    $tpl->print("MAIN");
		 
    if(scalar(@members) != 0) {
	my $tpm = new CGI::FastTemplate($config->{templates});
	$tpm->strict();
	$tpm->define( page        => "adm_ord_status/uncommitted_table.template");
	$tpm->assign( {} );
	$tpm->parse(MAIN => "page");
	$tpm->print("MAIN");

	foreach my $h (@members) {
	    my $tpr = new CGI::FastTemplate($config->{templates});
	    $tpr->strict();
	    $tpr->define( header      => "adm_ord_status/reminder_members.template");
	    $tpr->assign($h);
	    $tpr->parse( MAIN => "header");
	    $tpr->print("MAIN");
	}
    }
    
    print "</table></span></form></body></html>";		 
}

my %subs = ( 0 => \&set_status_0,
	     1 => \&set_status_1,
	     2 => \&set_status_2,
	     3 => \&set_status_3,
	     4 => \&set_status_4,
	     5 => \&set_status_5,
	     6 => \&set_status_6,
	     7 => \&set_status_7,
    );

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $vars = $cgi->Vars;
    my $sth;

    if ($config->{status} < 5) {
	$sth = prepare("SELECT rebuild_all_wh_headers();", $dbh);
	$sth->execute;
	$sth->finish;
	$dbh->commit;
    }

    if(not defined($vars->{ConfirmYes}) and
       not defined($vars->{Close}) and
	not defined($vars->{SendReminder})) {
        print_html($config, $cgi, $dbh);
	return;
    }

    my $reminder = defined($vars->{SendReminder});
    my $old_status = $status;
    if(defined($vars->{Confirm}) and not defined($vars->{SendReminder})) {
	$subs{($status + 1) % 8}($vars, $config, $cgi, $dbh);
	
	$sth = prepare('SELECT ord_no, ord_status FROM order_header', $dbh);
	$sth->execute;
	my $aref = $sth->fetchrow_arrayref;
	if(not defined($aref)) {
	    die "Could not get order no and status";
	}
	$sth->finish;

	($ord_no, $status) = @{$aref};
    }

    email_notice($reminder, $status, $config, $cgi, $dbh) 
	if($status != $old_status or defined($vars->{SendReminder}));

    print_html($config, $cgi, $dbh);
}

# create an email over status changes
sub email_notice {
    my ($reminder, $status, $config, $cgi, $dbh) = @_;
    my $body = "adm_ord_status/status-$status.template";
    my $subject;
    my $h;

    my $sth;
    return if($status == 0 or $status > 2);
    my @hrefs;

    my $email_vals = {};
    return if($status < 1 or $status > 2);
    $subject = "vokomokum - Shortages in your current order";

    # find user orders where some of their products have
    # shortages and their order is not a wholesale quantity
    my %notify;
    my $st = <<EOS
	SELECT join_name(a.mem_fname, a.mem_prefix, a.mem_lname) AS fullname, 
	a.mem_email AS email, m.pr_id, p.pr_desc, m.meml_qty, p.pr_wh_q, 
	w.whl_mem_qty FROM members as a, mem_line AS m, product AS p, 
	wh_line AS w WHERE m.ord_no = $ord_no AND w.ord_no = m.ord_no AND 
	m.mem_id = a.mem_id AND m.pr_id = p.pr_id AND w.pr_id = p.pr_id 
	AND (w.whl_mem_qty % p.pr_wh_q != 0) AND (m.meml_qty % p.pr_wh_q) != 0 
EOS
;
	
    $sth = prepare($st, $dbh);
    $sth->execute;
    while ($h = $sth->fetchrow_hashref) {
        $h->{at_least} = $h->{pr_wh_q} * int($h->{meml_qty} / $h->{pr_wh_q});
	$h->{text} = sprintf("%5d %-64.64s %4d %4d\n",
			     $h->{pr_id}, $h->{pr_desc}, $h->{meml_qty},
			     $h->{at_least});
	my $mem = $h->{email};
	$notify{$mem} = [] if(not defined($notify{$mem}));
	push @{$notify{$mem}}, $h;
    }
    $sth->finish;
    $dbh->commit;
    
    # crank out an email for each key in %notify
    foreach my $addr (keys %notify) {
	my @rows = sort @{$notify{$addr}};
	
	my $fh = email_header($addr, $subject, $config);
	email_chunk($fh, "shortage_1_txt.template", $rows[0], $config);
	foreach my $href (@rows) {
	    email_chunk($fh, "shortage_2_txt.template", $href, $config);
	}
	email_chunk($fh, "shortage_3_txt.template", $rows[0], $config);
	email_chunk($fh, "sig_txt.template", {}, $config);
	email_chunk($fh, "html_start.template", {}, $config);
	email_chunk($fh, "shortage_1_html.template", $rows[0], $config);
	foreach my $href (@rows) {
	    email_chunk($fh, "shortage_2_html.template", $href, $config);
	}
	email_chunk($fh, "shortage_3_html.template", $rows[0], $config);
	email_chunk($fh, "sig_html.template", {}, $config);
	close($fh);
    }
}

	
sub main {	     
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);

    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;
    my @stuff = localtime(time + 21 * 86400);
    $config->{order_name} = strftime("%d %B %Y", @stuff);

    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "Running as $program");

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    $config->{text}  = "Yes, really change it";
    $config->{button} = "ConfirmYes";
    $config->{reminder} = 0;
    $config->{reminder} = 1 if ($status == 1);
    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
