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

# sort by cat, subcat, desc alpha
sub pr_sort{
    my $aid = 100000 * $a->{pr_cat} + $a->{pr_sc};
    my $bid = 100000 * $b->{pr_cat} + $b->{pr_sc};
    my $cmp = ($sc_descs{$aid}->{sort_ord} <=> $sc_descs{$bid}->{sort_ord});
    return $cmp if($cmp != 0);
    return ($a->{pr_desc} cmp $b->{pr_desc});
}


# the relationship between db columns to input fields
my %db_2_vars = (
    mem_id       => "Member",
    mem_fname    => "Forename",
    mem_prefix   => "Prefix",
    mem_lname    => "Lastname",
    mem_street   => "Street",
    mem_house    => "Houseno",
    mem_flatno   => "Apt",
    mem_city     => "City",
    mem_postcode => "Postcode",
    mem_home_tel => "Homeph",
    mem_mobile   => "Mobile",
    mem_work_tel => "Workph",
    mem_email    => "Email",
    mem_bank_no  => "Account",
    mem_active   => "Active",
    mem_admin    => "Admin",
    mem_adm_adj  => "Spclacct",
    mem_message  => "Message",
    mem_adm_comment => "Comment",
    );

# this will turned into a input-field -> db column translation
my %vars_2_db;

sub trimstr {
    my ($key, $vars) = @_;
    
    my $str = $vars->{$key};
    return undef if(not defined($str));
    $str =~ s/^\s*//;
    $str =~ s/\s*$//;
    return $str;
}

# routine to get a member order
sub get_mem {
    my ($nextstate, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  checkout    => "adm_kassa/adm_kassa_checkout.template",
                  xfer        => "adm_kassa/adm_kassa_xfer.template",
	);
    my %h =(  Pagename    => "Select Member to Check Out",
	      Title       => "Select Member to Check Out",
	      Nextcgi     => "adm_kassa.cgi",
	      mem_name    => $config->{mem_name},
	      sel_state   => $nextstate,
	      from_id     => 0,
	      to_id       => 0,
	      check_out   => $config->{check_out},
	      check_out_name   => $config->{check_out_name},
	      Member      => "",
	      Forename    => "",
	      Lastname    => "",
	      Email       => "",
	      err_msgs    => "$err_msgs",
	);

    my $buttons = "checkout";
    if($nextstate == '4') {
	$h{Pagename} = $h{Title} = "Select member order to move items to";
	$h{from_id} = $config->{check_out};
	$h{to_id} = 0;
	$buttons = "xfer";
    }

    if($nextstate == '5') {
	$h{Pagename} = $h{Title} = "Select member order to receive items from";
	$h{to_id} = $config->{check_out};
	$h{from_id} = 0;
	$buttons = "xfer";
    }
   
    $tpl->assign(\%h);
    $tpl->parse(BUTTONS => $buttons);
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    if(length($err_msgs) > 0) {
	print "<span class=\"warn\"><big>$err_msgs</big></span>";
    }

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->assign(\%h);
    $tpl->parse(MAIN => "main");
    $tpl->print("MAIN");
    $dbh->commit;
    $dbh->disconnect;
    exit 0;
}

# state 1 - come here after getting (we hope) a member indication
sub state_1 {
    my ($vals, $config, $cgi, $dbh) = @_;

    if(defined($vals->{check_out}) and defined($vals->{Cancel})) {
	state_2($vals, $config, $cgi, $dbh);
    }

    # see if we can identify who is wanted from the input
    my $sel_cnt = 0;
    my @execvals;
    my $st = "FROM members as m, mem_order as o ";

    # ignore other info if member number given
    if(defined($vals->{Member}) and $vals->{Member} =~ /^\s*\d+\s*$/) {
	delete $vals->{Email} if(defined($vals->{Email}));
	delete $vals->{Lastname} if(defined($vals->{Lastname}));
	delete $vals->{Forename} if(defined($vals->{Forename}));
	$vals->{mem} = $vals->{Member};
    }

    # look for the following 3 input terms, count all non-blank entries
    foreach my $k (qw(Forename Lastname Email Member)) {
	if(defined($vals->{$k})) {
	    my $v = trimstr($k, $vals);
	    next if($v eq "");
	    if($k =~ /name/) {
		$v = "\%$v%";
		if($sel_cnt) {
		    $st .= " AND $vars_2_db{$k} ilike ?";
		} else {
		    $st .= " WHERE $vars_2_db{$k} ilike ?";
		}
	    }else {
		if($sel_cnt) {
		    $st .= " AND m.$vars_2_db{$k} = ?";
		} else {
		    $st .= " WHERE m.$vars_2_db{$k} =  ?";
		}
	    }
	    push @execvals, $v;
	    $sel_cnt++;
	}
    }
    if($sel_cnt == 0) {
	$st .= " WHERE ";
    } else {
	$st .= " AND ";
    }

    $st .= "m.mem_id = o.mem_id AND o.ord_no=?";
    push @execvals, $ord_no;
    my $cmd = "SELECT count(*) $st";

    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute(@execvals);
    };

    my $aref;
    if(! $@ ) {
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
	$dbh->rollback;
    }

    if($@ or not defined($aref) or $aref->[0] == 0) {
	$err_msgs .= "<br>No member matches your selection or there is no order for this member<br>";
	get_mem($vals->{sel_state}, $config, $cgi, $dbh);
    }

    $cmd = "SELECT m.mem_id, m.mem_lname, m.mem_fname, m.mem_prefix, " .
	"m.mem_email, m.mem_street, m.mem_house, m.mem_flatno, ".
	"join_name(m.mem_fname, m.mem_prefix, m.mem_lname) AS fullname, ".
	" o.mo_checked_out $st". 
	" ORDER BY lower(m.mem_lname), lower(m.mem_fname), lower(m.mem_prefix)";
    $sth = prepare($cmd, $dbh);

    $sth->execute(@execvals);
    my $href;
    if($aref->[0] == 1) {
	$href = $sth->fetchrow_hashref;
	$sth->finish;
	$dbh->commit;
	# we have a match, 
	$vals->{mem} = $href->{mem_id};

	if($vals->{sel_state} == 1) {
	    $config->{check_out} = $vals->{mem};
	    $config->{check_out_name} = $href->{fullname};
	    state_2($vals, $config, $cgi, $dbh);
	}
	if($vals->{sel_state} == 4) {
	    $config->{from_id} = $config->{check_out} = $vals->{check_out};
	    $config->{to_id} = $vals->{mem};
	    state_4($vals, $config, $cgi, $dbh);
	}
	if($vals->{sel_state} == 5) {
	    $config->{to_id} = $config->{check_out} = $vals->{check_out};
	    $config->{from_id} = $vals->{mem};
	    state_5($vals, $config, $cgi, $dbh) 
	}
    }

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  buttons     => "adm_kassa/adm_kassa_memlist.template",
		  xfer        => "adm_kassa/adm_kassa_xfer_memlist.template",
	);
    my %h =(  Pagename    => "Select Member to Check Out",
	      Title       => "Select Member to Check Out",
	      Nextcgi     => "adm_kassa.cgi",
	      mem_name    => $config->{mem_name},
	      sel_state   => $config->{sel_state},
	      from_id     => 0,
	      to_id       => 0,
	      check_out   => $config->{check_out},
	      check_out_name   => $config->{check_out_name},
	      Member      => "",
	      Forename    => "",
	      Lastname    => "",
	      Email       => "",
	      err_msgs    => "$err_msgs",
	);

    my $buttons = "buttons";
    if($config->{sel_state} == '4') {
	$h{Pagename} = $h{Title} = "Select member order to move items to";
	$h{from_id} = $config->{check_out};
	$h{to_id} = 0;
	$buttons = "xfer";
    }

    if($config->{sel_state} == '5') {
	$h{Pagename} = $h{Title} = "Select member order to get items from";
	$h{to_id} = $config->{check_out};
	$h{from_id} = 0;
	$buttons = "xfer";
    }
   

    $tpl->assign(\%h);
    $tpl->parse(BUTTONS => "$buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( 
	row         => "adm_kassa/adm_kassa_memlist_row.template",
	);

    my $selected = "SELECTED";
    while(my $href = $sth->fetchrow_hashref) {
	my $tpl = new CGI::FastTemplate( $config->{templates} );
	$tpl->define(row => "adm_kassa/adm_kassa_memlist_row.template"); 
	$tpl->assign({
	    mem_id       => $href->{mem_id},
	    mem_fname    => escapeHTML($href->{mem_fname}), 
	    mem_prefix   => escapeHTML($href->{mem_prefix}),
	    mem_lname    => escapeHTML($href->{mem_lname}), 
	    mem_email    => escapeHTML($href->{mem_email}),
	    mem_street   => escapeHTML($href->{mem_street}),
	    mem_house    => escapeHTML($href->{mem_house}),
	    mem_flatno   => escapeHTML($href->{mem_flatno}),
	    checked_out  => ($href->{mo_checked_out}) ? "Checked Out" : "", 
	    Selected     => $selected,
		     }
	    );

	$tpl->parse(MAIN => "row");
	$tpl->print;
	$tpl = undef;
	$selected = "";
    }
    $sth->finish;
    $dbh->commit;
    print "</table></form></body></html>";
    $dbh->disconnect;
    exit 0;
}

# find out which member they picked from list
sub state_11 {
    my ($vals, $config, $cgi, $dbh) = @_;

    my $v = $vals->{selected_row};
    $v =~ s/m_//;
    $vals->{mem} = $v;
    if($vals->{sel_state} == 4) {
	$config->{to_id} = $v;
	state_4($vals, $config, $cgi, $dbh);
    }
    if($vals->{sel_state} == 5) {
	$config->{from_id} = $v;
	state_5($vals, $config, $cgi, $dbh);
    }
    $vals->{Member} = $v;
    state_1($vals, $config, $cgi, $dbh);

}

sub disp_xfer {
    my ($width, $vals, $config, $cgi, $dbh) = @_;
    my $sth = prepare("SELECT * FROM xfer WHERE (from_id = ? OR to_id = ?) ".
		      "AND ord_no = ? ORDER BY pr_id", $dbh);
    $sth->execute($config->{check_out}, $config->{check_out}, $ord_no);

    while(my $h = $sth->fetchrow_hashref) {
	my $dir = ($config->{check_out} == $h->{from_id});
	my $href = {
	    verb    =>  (($dir) ? "Transferred" : "Received"),
	    to_from => ($dir) ? "to" : "from",
	    wid     => $width - 2,
	    qty     => $h->{qty},
	    xfer_id => ($dir) ? $h->{to_id} : $h->{from_id},
	    pr_id   => $h->{pr_id},
	};
	my $tpl = new CGI::FastTemplate( $config->{templates} );
	$tpl->define(row => "adm_kassa/adm_kassa_xfer_rpt.template"); 
	$tpl->strict;
	$tpl->assign($href);
	$tpl->parse(MAIN => "row");
	$tpl->print;
	$tpl = undef;
    }

    $sth->finish;
    $dbh->commit;
}

sub get_xfout {
    my ($pr, $vals, $config, $cgi, $dbh) = @_;

    my $sth = prepare("SELECT * FROM xfer WHERE from_id = ? AND to_id = ? ".
		      "AND ord_no = ? ", $dbh);
    $sth->execute($config->{check_out}, $config->{to_id}, $ord_no);
    foreach my $meml (keys %{$pr}) {
	$pr->{$meml}->{meml_xfer_out} = 0;
    }

    while(my $h = $sth->fetchrow_hashref) {
	next if(not defined($pr->{$h->{pr_id}}));
	$pr->{$h->{pr_id}}->{meml_xfer_out} = $h->{qty};
    }

    $sth->finish;
    $dbh->commit;
}

sub get_xfin {
    my ($pr, $vals, $config, $cgi, $dbh) = @_;

    my $sth = prepare("SELECT * FROM xfer WHERE from_id = ? AND to_id = ? ".
		      "AND ord_no = ? ", $dbh);
    $sth->execute($config->{from_id}, $config->{check_out}, $ord_no);
    foreach my $meml (keys %{$pr}) {
	$pr->{$meml}->{meml_xfer_in} = 0;
    }

    while(my $h = $sth->fetchrow_hashref) {
	next if(not defined($pr->{$h->{pr_id}}));
	$pr->{$h->{pr_id}}->{meml_xfer_in} = $h->{qty};
    }

    $sth->finish;
    $dbh->commit;
}


my %pymnts = ( stgeld_rxed => {col => 'mo_stgeld_rxed', type =>'&nbsp;', 
			      desc=>"Statiegeld for items in this order", ord => 0},
	      stgeld_refunded => {col => 'mo_stgeld_refunded', type=>'Credit', 
				  desc=>'Statiegeld repaid to member', ord => 1},
	      crates_rxed => {col => 'mo_crates_rxed', type =>'&nbsp;', 
			      desc=>"Deposit for crates with this order", ord => 2},
	      crates_refunded => {col => 'mo_crates_refunded', type=>'Credit', 
				  desc=>"Deposit returned for crates", ord => 3},
	      membership => {col => 'mo_membership', type =>'&nbsp;', 
			    desc=>"Membership fees", ord => 4},
	      misc_rxed => {col => 'mo_misc_rxed', type =>'&nbsp;', 
			    desc=>"Miscellaneous charges (see notes)", ord => 5},
	      misc_refunded => {col => 'mo_misc_refunded', type=>'Credit', 
				desc => "Miscellaneous credits (see notes)", ord => 6},
	      vers_rxed  => {col => 'mo_vers', type=>'&nbsp', 
				desc => "Vers (groente, kaas, eiren)", ord => 7},
);

sub posted_pymnts {
    my ($mhref, $vals, $config, $cgi, $dbh) = @_;

    my $sth;
    foreach my $col (keys %pymnts) {
	my $dbcol = $pymnts{$col}->{col};
	if(defined($vals->{$col})) {
	    my $v = $vals->{$col};
	    $v =~ s/,/./g;
	    $v = '0.0' if($v eq "");
	    $v = int(100 * $v);
	    if($v != $mhref->{$dbcol}) {
		$sth = prepare("UPDATE mem_order SET $dbcol = ? WHERE mem_id = ? ".
		   "AND ord_no = ?", $dbh);

		$sth->execute($v, $config->{check_out}, $ord_no);
		$dbh->commit;
		$mhref->{$dbcol} = $v;
	    }
	}
    }

    if(defined($vals->{notes})) {
	$sth = prepare("DELETE FROM order_notes WHERE mem_id = ? AND ord_no = ?", $dbh);
	$sth->execute($config->{check_out}, $ord_no);
	$sth = prepare("INSERT INTO order_notes (note, mem_id, ord_no) ".
		       " VALUES (?, ?, ?)", $dbh);
	$sth->execute($vals->{notes}, $config->{check_out}, $ord_no);
    }

    $dbh->commit;
}

# process posted damage reports
sub posted_damaged {
    my ($pr, $vals, $config, $cgi, $dbh) = @_;

    my $sth = prepare("SELECT broken_missing(?, ?, ?, ?,  True)", $dbh);
    foreach my $dpr (keys %{$vals}) {
	next if($dpr !~ /d_(\d+)/);
	my $pid = $1;
	next if(not defined($pr->{$pid}));
	my $v = $vals->{$dpr};
	eval {
	    $sth->execute($config->{check_out}, $ord_no, $pid, $v);
	};
	if($@) {
	    my $e = $@;
            $e =~ s/.*ERROR: *//;
	    $e =~ s/\sat \/.*$//;
	    $err_msgs .= "<br>$e>";
	    $dbh->rollback;
	} else {
	    $pr->{$pid}->{meml_damaged} = $v;
	}
	$dbh->commit;
    }
}

# process posted damage reports
sub posted_missing {
    my ($pr, $vals, $config, $cgi, $dbh) = @_;

    my $sth = prepare("SELECT broken_missing(?, ?, ?, ?, False)", $dbh);
    foreach my $dpr (keys %{$vals}) {
	next if($dpr !~ /mi_(\d+)/);
	my $pid = $1;
	next if(not defined($pr->{$pid}));
	my $v = $vals->{$dpr};
	eval {
	    $sth->execute($config->{check_out}, $ord_no, $pid, $v);
	};
	if($@) {
	    my $e = $@;
            $e =~ s/.*ERROR: *//;
	    $e =~ s/\sat \/.*$//;
	    $err_msgs .= "<br>$e";
	    $dbh->rollback;
	} else {
	    $pr->{$pid}->{meml_missing} = $v;
	}
	$dbh->commit;
    }
}

sub posted_xfer {
    my ($vals, $config, $cgi, $dbh) = @_;
    
    my $sth = prepare("SELECT xfer_order(?, ?, ?, ?, ?)", $dbh);
    foreach my $key (keys %{$vals}) {
	if($key =~ /^(x[io])_(\d+)_(\d+)/) {
	    my $dir = $1;
	    my $tgt = $2;
	    my $pid = $3;

	    if ($dir eq 'xi') {
		next if($tgt == $config->{check_out});
		$config->{from_id} = $tgt;
		$config->{to_id} = $config->{check_out};
	    } else {
		next if($dir ne 'xo' or $tgt == $config->{check_out});
		$config->{to_id} = $tgt;
		$config->{from_id} = $config->{check_out};
	    }
	    eval {
		$sth->execute($config->{from_id}, $config->{to_id}, $ord_no, 
			      $pid, $vals->{$key});
	    };
	    if($@) {
		my $e = $@;
		$e =~ s/.*ERROR: *//;
		$e =~ s/\sat \/.*$//;
		$err_msgs .= "<br>$e";
		$dbh->rollback;
	    }
	    $dbh->commit;
	}
    }    
}

# check if membership paid
sub membership_paid {
    my ($config, $cgi, $dbh) = @_;
    my $sth = prepare("SELECT mem_membership_paid FROM members ".
		      "WHERE mem_id = ?", $dbh);
    $sth->execute($config->{check_out});
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    $dbh->commit;
    return $h->{mem_membership_paid};
}

# display (maybe editable) payment lines
sub disp_payments {
    my ($width, $mhref, $vals, $config, $cgi, $dbh) = @_;

    my %h;
    foreach my $col (sort {$pymnts{$a}->{ord} <=> $pymnts{$b}->{ord}} keys %pymnts) {
	my $dbcol = $pymnts{$col}->{col};

	next if($dbcol eq 'mo_membership' and 
		membership_paid($config, $cgi, $dbh)  and 
		$mhref->{$dbcol} == 0);
	my $tpl = new CGI::FastTemplate($config->{templates});
	$tpl->strict;
	$tpl->define( row => ($mhref->{mo_checked_out}) ?
		      "adm_kassa/adm_kassa_py_noedit.template" :
		      "adm_kassa/adm_kassa_py_edit.template");
	$h{desc} = $pymnts{$col}->{desc};
	$h{credit} = $pymnts{$col}->{type};
	$h{amount} = sprintf "%0.2f", $mhref->{$dbcol}/100.0;
	$h{name} = $col;
	$h{width} = $width - 2;
	$tpl->assign(\%h);
	$tpl->parse(MAIN => "row");
	$tpl->print;
	$tpl = undef;
    }
}
  
# display the various totals
sub disp_totals {
    my ($width, $vals, $config, $cgi, $dbh) = @_;

    my $sth = prepare("SELECT order_totals(?, ?)", $dbh);
    $sth->execute($config->{check_out}, $ord_no);

    my $a = $sth->fetchrow_arrayref;
    
    my $str = $a->[0];
    $sth->finish;
    $dbh->commit;
    $str =~ s/[()]//g;
    # tots is tot @ rate, btw-owed, btw-rate (3x, 0, 6, 19%
    # then toto ex-btw, tot btw, tot inc btw
    my @tots = split(/,/, $str);
    for(my $i = 0; $i < 3; ++$i) {
	my $subt = shift @tots;
	my $owed = shift @tots;
	my $rate = shift @tots;
	#next if($subt == 0);
	#$subt = sprintf "%0.2f", $subt/100.;
	#$owed = sprintf "%0.2f", $owed/100.;
	#print "<tr class=\"myorder\"><td align=\"left\" colspan=\"$w\">".
	#    "Total of items at $rate% BTW</td>".
	#    "<td align=\"right\">$subt</td></tr>\n".
	#    "<tr class=\"myorder\"><td align=\"left\" colspan=\"$w\">\n".
	#    "Total BTW at $rate%</td>".
	#    "<td align=\"right\">$owed</td></tr>\n";
    }
    shift @tots;
    shift @tots;
    my $total = shift @tots;
    $total = sprintf "%0.2f", $total/100.0;

    $sth = prepare("SELECT note FROM order_notes WHERE mem_id = ? AND ord_no = ?", $dbh);
    $sth->execute($config->{check_out}, $ord_no);
    my $note = "";
    my $n = $sth->fetchrow_arrayref;
    $sth->finish;
    $note = $n->[0] if(defined($n));

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict;
    $tpl->define( row => "adm_kassa/adm_kassa_order_ftr.template" );
    my $h = { wid    => $width -1,
	      total  => $total,
	      note   => $note,
    };
    $tpl->assign($h);
    $tpl->parse(MAIN => "row");
    $tpl->print;
    $dbh->disconnect;
    exit 0;
}

# start checkout process, we have a member number
sub state_2 {
    my ($vals, $config, $cgi, $dbh) = @_;
    my $sth;

    if(defined($vals->{Xfer_Out})) {
	$config->{sel_state} = 4;
	get_mem(4,  $config, $cgi, $dbh);
    }

    if(defined($vals->{Xfer_In})) {
	$config->{sel_state} = 5;
	get_mem(5, $config, $cgi, $dbh);
    }

    $sth = prepare("UPDATE mem_order SET mo_checked_out = False ".
		       "WHERE mem_id = ? AND ord_no = ?", $dbh);
    if(defined($vals->{Reopen})) {
	$sth->execute($config->{check_out}, $ord_no);
	$sth->finish;
	$dbh->commit;
    }

    $sth = prepare("UPDATE mem_order SET mo_checked_out = True, ".
		   "mo_checked_out_by = ? WHERE mem_id = ? ".
		   "AND ord_no = ?", $dbh);
    if(defined($vals->{Close})) {
	$sth->execute($config->{mem_id}, $config->{check_out}, $ord_no);
	$sth->finish;
	$dbh->commit;
    }

    posted_xfer($vals, $config, $cgi, $dbh);

    $sth = prepare("SELECT * FROM mem_order WHERE mem_id = ? ".
		      "AND ord_no = ?", $dbh);
    $sth->execute($config->{check_out}, $ord_no);
    my $mhref = $sth->fetchrow_hashref;

    $sth = prepare("SELECT * FROM mem_line as m, product as p WHERE m.mem_id = ? " .
		   "AND m.ord_no = ? AND m.pr_id = p.pr_id", $dbh);
    $sth->execute($config->{check_out}, $ord_no);
    my %pr;
    my $href;
    while($href = $sth->fetchrow_hashref) {
	$pr{$href->{pr_id}} = $href;
    }

    # process any payment stuff
    posted_pymnts($mhref, $vals, $config, $cgi, $dbh);
    posted_damaged(\%pr, $vals, $config, $cgi, $dbh);
    posted_missing(\%pr, $vals, $config, $cgi, $dbh);

    $sth->execute($config->{check_out}, $ord_no);
    my %prx;

    while($href = $sth->fetchrow_hashref) {
	$prx{$href->{pr_id}} = $href;
    }
    $config->{title_row} = "adm_kassa/adm_kassa_title.template";
    $config->{row} = "adm_kassa/adm_kassa_noedit_prrow.template";
    if(defined($vals->{Missing})) {
	$config->{row} = "adm_kassa/adm_kassa_edit_missing.template";
    } elsif (defined($vals->{Damaged})) {
	$config->{row} = "adm_kassa/adm_kassa_edit_damaged.template";
    } elsif(defined($config->{to_id}) and $config->{to_id} and
	     $config->{to_id} != $config->{check_out}
	     and $config->{sel_state} == 4) {
	$config->{title_row} = "adm_kassa/adm_kassa_xfer_title.template";
	$config->{row} = "adm_kassa/adm_kassa_edit_xferout.template";
	get_xfout(\%prx, $vals, $config, $cgi, $dbh);
    }

    my @products;
    my $h;
    foreach my $k (keys %prx) { 
	push @products, $prx{$k}; 
    }
    my @sorted = sort pr_sort @products;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  open_buttons   => "adm_kassa/adm_kassa_payments.template",
                  closed_buttons => "adm_kassa/adm_kassa_reopen.template",
	);
    my %h =(  Pagename    => "Checkout Member $config->{check_out} $config->{check_out_name}",
	      Title       => "Checkout Member $config->{check_out} $config->{check_out_name}",
	      Nextcgi     => "adm_kassa.cgi",
	      mem_name    => $config->{mem_name},
	      sel_state   => 2,
	      from_id     => 0,
	      to_id       => 0,
	      check_out   => $config->{check_out},
	      check_out_name => $config->{check_out_name},
	      err_msgs    => "$err_msgs",
	);

    my $buttons = ($mhref->{mo_checked_out}) ?
	"closed_buttons" : "open_buttons";
    $h{BUTTONS} = "" if($status != 7); 
    $tpl->assign(\%h);
    $tpl->parse(BUTTONS => "$buttons") if($status == 7);
	
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    if($status != 7) {
	$err_msgs = "<br>This order is not at the pickup stage<br>"; 
	print "<span class=\"warn\" align-\center\"><strong> $err_msgs</strong></span>\n";
	print "</form></body></html>";
	$dbh->disconnect;
	exit 0;
    }
    my $line = 0;
    my $dir = ($config->{from_id} == $config->{check_out});
    foreach $h (@sorted) {
	if($line++ % 20 == 0) {
	    $tpl = new CGI::FastTemplate($config->{templates});
	    $tpl->define(row => $config->{title_row});
	    $tpl->assign({width        => 9,
			  verb         =>  (($dir) ? "Transferred" : "Received"),
			  to_from      => (($dir) ? "to" : "from"),
			  other_mem_id => (($dir) ? $config->{to_id} : $config->{from_id}),
			 });
	    $tpl->parse(MAIN => "row");
	    $tpl->print;
	    $tpl = undef;
	}

	$h->{cost_inc_btw} = sprintf "%0.2f", $h->{meml_unit_price} * 
	    $h->{meml_pickup}/100.0;
	$h->{meml_unit_price} = sprintf "%0.2f", $h->{meml_unit_price} / 100.0;
	$h->{to_id} = $config->{to_id};
	$h->{from_id} = $config->{from_id};
	$h->{RowClass} = "myorder";
	$tpl = new CGI::FastTemplate($config->{templates});
	$tpl->strict;
	my $url_temp = "common/dnb_url.template";
	if ( $h->{pr_wh} == $config->{DNB}->{dnb_wh_id} ) {
            if ( $h->{wh_prcode} < 10000 ) {
                $h->{PID} = sprintf "%04.4d", $h->{wh_prcode};
            }
	} elsif($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} else {
	    $h->{URL} = "";
	}

	$tpl->define(row => $config->{row},
		     url => $url_temp);
	$tpl->assign($h);
	$tpl->parse("URL", "url");
	    
	$tpl->parse(MAIN => "row");
	$tpl->print;
	$tpl = undef;
    }

    disp_xfer(9, $vals, $config, $cgi, $dbh);
    disp_payments(9, $mhref, $vals, $config, $cgi, $dbh);
    disp_totals(9, $vals, $config, $cgi, $dbh);
    $dbh->disconnect;
    exit 0;
}

# we think we have a member order to move stuff to
sub state_4 {
    my ($vals, $config, $cgi, $dbh) = @_;
    state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));

    my $sth = prepare("SELECT mo_checked_out FROM mem_order WHERE mem_id = ? ".
		      "AND ord_no = ?", $dbh);

    $sth->execute($config->{check_out}, $ord_no);
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    if(not defined($h)) {
	$err_msgs = "<br>Can't find an order for member $config->{check_out}";
	$config->{sel_state} = 0;
	state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));
    }
    if($h->{mo_checked_out}) {
	$err_msgs = "br>The order for member $vals->{mem} has been checked out, ".
	    "you will have to re-open it";
	$config->{sel_state} = 0;
	state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));
    }
    
    $config->{to_id} = $vals->{mem};

    state_2($vals, $config, $cgi, $dbh);
}

sub state_5 {
    my ($vals, $config, $cgi, $dbh) = @_;
    state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));
    my $sth = prepare("SELECT mo_checked_out FROM mem_order WHERE mem_id = ? ".
		      "AND ord_no = ?", $dbh);

    $sth->execute($config->{from_id}, $ord_no);
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    if(not defined($h)) {
	$err_msgs = "<br>Can't find an order for member $vals->{mem}";
	$config->{sel_state} = 0;
	state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));
    }
    if($h->{mo_checked_out}) {
	$err_msgs = "<br>The order for member $config->{from_id} has been checked out, ".
	    "you will have to re-open it";
	$config->{sel_state} = 0;
	state_2($vals, $config, $cgi, $dbh) if(not defined($vals->{mem}));
    }
    
    # first handle any update records posted
    posted_xfer($vals, $config, $cgi, $dbh);

    $sth = prepare("SELECT * FROM mem_order WHERE mem_id = ? ".
		      "AND ord_no = ?", $dbh);
    $sth->execute($config->{check_out}, $ord_no);
    my $mhref = $sth->fetchrow_hashref;
    # we need a copy of the member being checked out
    $sth = prepare("SELECT * FROM mem_line as m, product as p WHERE m.mem_id = ? " .
		   "AND m.ord_no = ? AND m.pr_id = p.pr_id", $dbh);
    $sth->execute($config->{check_out}, $ord_no);
    my %pr;
    my $href;
    while($href = $sth->fetchrow_hashref) {
	$pr{$href->{pr_id}} = $href;
    }

    # process any payment stuff
    posted_pymnts($mhref, $vals, $config, $cgi, $dbh);
    posted_damaged(\%pr, $vals, $config, $cgi, $dbh);
    posted_missing(\%pr, $vals, $config, $cgi, $dbh);
    
    $config->{to_from} = $vals->{mem};
    $config->{title_row} = "adm_kassa/adm_kassa_xfer_title.template";
    $config->{row} = "adm_kassa/adm_kassa_edit_xferin.template";
    
    $sth->execute($config->{from_id}, $ord_no);
    my %prx;
    while($href = $sth->fetchrow_hashref) {
	$prx{$href->{pr_id}} = $href;
    }
    get_xfin(\%prx, $vals, $config, $cgi, $dbh);
    my @products;
    foreach my $k (keys %prx) { 
	push @products, $prx{$k}; 
    }


    my @sorted = sort pr_sort @products;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  open_buttons   => "adm_kassa/adm_kassa_xfer_payments.template",
	);
    my %h =(  Pagename    => "Transfer Items from Order for Member $config->{from_id}",
	      Title       => "Transfer Items from Order for Member $config->{from_id}",
	      Nextcgi     => "adm_kassa.cgi",
	      mem_name    => $config->{mem_name},
	      sel_state   => 2,
	      from_id     => $config->{from_id},
	      to_id       => $config->{to_id},
	      check_out   => $config->{check_out},
	      check_out_name   => $config->{check_out_name},
	      err_msgs    => "$err_msgs",
	);

    $tpl->assign(\%h);
    $tpl->parse(BUTTONS => "open_buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    my $line = 0;
    my $dir = ($config->{from_id} == $config->{check_out});
    foreach $h (@sorted) {
	if($line++ % 20 == 0) {
	    $tpl = new CGI::FastTemplate($config->{templates});
	    $tpl->define(row => $config->{title_row});
	    $tpl->assign({width        => 9,
			  verb         =>  (($dir) ? "Transferred" : "Received"),
			  to_from      => (($dir) ? "to" : "from"),
			  other_mem_id => (($dir) ? $config->{to_id} : $config->{from_id}),
			 });
	    $tpl->parse(MAIN => "row");
	    $tpl->print;
	    $tpl = undef;
	}

	$h->{cost_inc_btw} = sprintf "%0.2f", $h->{meml_unit_price} * 
	    $h->{meml_pickup}/100.0;
	$h->{meml_unit_price} = sprintf "%0.2f", $h->{meml_unit_price} / 100.0;
	$h->{to_id} = $config->{to_id};
	$h->{from_id} = $config->{from_id};
	$h->{RowClass} = "editok";
	$tpl = new CGI::FastTemplate($config->{templates});
	$tpl->strict;
	my $url_temp = "common/dnb_url.template";
	if ( $h->{pr_wh} == $config->{DNB}->{dnb_wh_id} ) {
            if ( $h->{wh_prcode} < 10000 ) {
                $h->{PID} = sprintf "%04.4d", $h->{wh_prcode};
            }
	} elsif($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} else {
	    $h->{URL} = "";
	}

	$tpl->define(row => $config->{row},
		     url => $url_temp);
	$tpl->assign($h);
	$tpl->parse("URL", "url");

	$tpl->parse(MAIN => "row");
	$tpl->print;
	$tpl = undef;
    }

    print "</table></form></body></html>";
    $dbh->disconnect;
    exit 0;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);

    map {$vars_2_db{$db_2_vars{$_}}=$_} keys(%db_2_vars);
    my $vars = $cgi->Vars;
    $config->{check_out} = ($vars->{check_out})
	if(defined($vars->{check_out}));
    $config->{check_out_name} = ($vars->{check_out_name})
	if(defined($vars->{check_out_name}));
    $config->{from_id} = ($vars->{from_id})
	if(defined($vars->{from_id}));
    $config->{to_id} = ($vars->{to_id})
	if(defined($vars->{to_id}));
    $config->{sel_state} = ($vars->{sel_state})
	if(defined($vars->{sel_state}));

    get_mem(1, $config, $cgi, $dbh) 
	if(not defined($vars->{state}));
    state_1($vars, $config, $cgi, $dbh) if($vars->{state} == 1);
    state_11($vars, $config, $cgi, $dbh) if($vars->{state} == 11);
    state_2($vars, $config, $cgi, $dbh) if($vars->{state} == 2);
    state_4($vars, $config, $cgi, $dbh) if($vars->{sel_state} == 4);
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
