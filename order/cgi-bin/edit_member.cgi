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
use Crypt::PasswdMD5;
use voko;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $status;
my $err_msgs = "";
my $input_err = 0;
my $new_member = 0;

# how to deal with input fields
my %inputs = (
    Forename => {req => 1, typ =>"text", desc=>"First Name"},
    Prefix   => {req => 0, typ =>"text"},
    Lastname => {req => 1, typ =>"text", desc=>"Last Name"},  
    Email    => {req => 1, typ =>"email", desc=>"Email address"},
    Street   => {req => 1, typ =>"text", desc=>"Street Name"},
    Houseno  => {req => 1, typ =>"num", desc=>"House number"},
    Apt      => {req => 0, typ =>"text"},
    City     => {req => 1, typ =>"text", desc=>"City"},
    Postcode => {req => 1, typ =>"postcode", desc=>"Postcode"},
    Account  => {req => 1, typ =>"bankacct", desc=>"Bank account number"},
    Homeph   => {req => 0, typ =>"telno", desc=>"Home telephone number"},
    Workph   => {req => 0, typ =>"telno", desc=>"Work telephone number"},
    Mobile   => {req => 0, typ =>"telno", desc=>"Mobile telephone number"},
    Mem_Paid => {req => 0, typ =>"check"},
    Active   => {req => 0, typ =>"check"},
    Admin    => {req => 0, typ =>"check"},
    Spclacct => {req => 0, typ =>"check"},
    Pwd0     => {req => 0, typ =>"pwd0", desc=>"Password"},
    Message  => {req => 0, typ =>"text", desc=>"Message"},
    Comment  => {req => 0, typ =>"text", desc=>"Comment"},
    );

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
    mem_membership_paid => "Mem_Paid",
    mem_admin    => "Admin",
    mem_adm_adj  => "Spclacct",
    mem_message  => "Message",
    mem_adm_comment => "Comment",
    );

# this will be turned into a input-field -> db column translation
my %vars_2_db;

# the values we will put into the databse on update/insert
my %sql;

sub get_postcode {
    my ($vars, $where ) = @_;

    my $pc = $vars->{Postcode};
    return -1  if(not defined($pc));
    return -2 if($pc !~ /^\s*(\d\d\d\d)\s*([a-z][a-z])\s*$/i);
    $$where = sprintf "%s %s", $1, uc $2;
    return 1;
}

sub trimstr {
    my ($key, $vars) = @_;
    
    my $str = $vars->{$key};
    return undef if(not defined($str));
    $str =~ s/^\s*//;
    $str =~ s/\s*$//;
    return $str;
}

# canonicalise a telephone number string
# return 1 if OK
# o if empty
# -1 if not Netherlands
# -2 strange character in string
# -3 wrong length
# -4 dialing code not 2 or 3 digits
# -5 wrong length
sub telno {
    my ($str, $where) = @_;
    if(!defined($str) or $str eq "") {
	$$where = "";
	return 0;
    }

    # discard country code if found and it's NL
    $str =~ s/^\+/00/;
    if($str =~ /^00/) {
	if($str !~ /0031\s*(.*)/) {
	    return -1;   # too far away
	}
	$str = "0$1";    # create dialing code
    }
    my $digs = $str;       # make a digits only version
    $digs =~ s/[() -]//g;
    return -2 if($digs !~ /^\d+/); # which did not work...
    if($digs =~ /^(06)/) {
	if($digs =~ /^06(\d\d)(\d\d\d)(\d\d\d)$/) {
	    $$where ="06 $1 $2 $3";
	    return 1;
	} else {
	    return -3;   # too long or too short
	}
    }
    $str =~ s/[ ()-]+/ /g; # collapse all separators to one
    $str =~ s/^\s//;       # trim the result
    $str =~ s/\s$//;
    # does it start with a dialing code?
    if($digs =~ /^0\d\d\d\d\d\d\d\d\d$/) {
	# see if member gave a separator for dialing code
	if($str =~ /^(0\d+) ([\d ]+)$/) {
	    # yep - break number up using member's guidance
	    my $dc = $1;
	    $str = $2;
	    $str =~ s/ //g;
	    return -4 if (length($dc) < 3 or length($dc) > 4);
	    if(length($dc) == 3) {
		# 3 digit dialing code
		$digs =~ /^(0\d\d)(\d\d\d)(\d\d)(\d\d)$/;
		$$where = "($1) $2 $3 $4";
		return 1;
	    } 
	    # 4 digit dialing code
	    $digs =~ /^(0\d\d\d)(\d\d)(\d\d)(\d\d)$/;
	    $$where = "($1) $2 $3 $4";
	    return 1;
	}
	# assume 3 digit dialing code
	$digs =~ /^(0\d\d)(\d\d\d)(\d\d)(\d\d)$/;
	$$where = "($1) $2 $3 $4";
	return 1;
    }
    # no dialing code, better be 7 digits, guess at 020
    return -5 if($digs !~ /^(\d\d\d)(\d\d)(\d\d)$/);
    $$where = "(020) $1 $2 $3";
    return 1;
}

# cananocolise bank acct no, return -1 if invalid, 0 if blank, 1 if OK
sub get_account_no {
    my ($str, $where) = @_;

    return 0 if(!defined($str) or $str eq "");
    $str =~ s/[ -]+//g; # collapse all separators to one
    $str =~ s/^\s//;       # trim the result
    $str =~ s/\s$//;
    return -1 if($str !~ /^\d+/);
    my @digs = split(//, $str);
    $$where = $str;
    if(length($str) < 4) {
	return 1;
    } elsif (length($str) == 4) {
	$str =~ /^(\d\d)(\d\d)$/;
	$$where =  "$1 $2";
	return 1;
    } elsif (length($str) < 7) {
	$str =~ /^(.*)(\d\d\d)$/;
	$where =  "$1 $2";
	return 1;
    } elsif(length($str) < 9) {
	$str =~ /^(.*)(\d\d)(\d\d\d\d)$/;
	$$where =  "$1 $2 $3";
	return 1;
    }
    my $sum = 0;

    for(my $mult = 9; $mult > 0; --$mult) {
	my $d = shift @digs;
	$sum += $d * $mult;
    }
    return -2 if($sum % 11);
    $str =~ /^(\d\d)(\d\d)(\d\d)(\d\d\d)$/;
    $$where =  "$1 $2 $3 $4";
    return 2;
}
    
# canoncolise email addr, return 1 if looks OK
# 0  = blank
# -1 = unused
# -2 = no lhs, no domain
# -3 = percent ni lhs
# -4 = leading minus, trailing - '-.', '.-', '..', '--'
# -5 = rhs contains non letter/number/., minus, undersocre
# -6 = 
sub get_email {
    my ($em, $where) = @_;

    return 0 if(not defined($em));
    return 0 if($em eq "");
    # no funnies in lhs
    return -2 if($em !~ /^(.+)\@(.*\.[^,]+)$/);
    # no double -'s leading, or leading/trailing - in any domani part

    my ($lhs, $rhs) = (lc $1, lc $2);
    return -3 if($lhs =~ /[%\@]/);
    return -4 if($rhs =~ /^-/ or $rhs =~ /[.-]$/ or 
		 $rhs =~ /[.-][.-]/);
    return -5 if($rhs !~ /^[a-z0-9_.-]+$/);
    return -6 if($lhs =~ /[\x01-\x1f]/);
    $$where =  "$lhs\@$rhs";
    return 1;
}

# get back the member record for a given mem_id, return undef on failure
sub get_member_data {
    my ($parse_hash, $vals, $dbh) = @_;


    if(!defined($vals->{mem}) or $vals->{mem} == 0) {
	$parse_hash->{new_member} = 1;
	return undef;
    }
    # try to get the existing member data
    my $sth = prepare('SELECT * FROM members WHERE mem_id = ?', $dbh);
    $sth->execute($vals->{mem});
    my $h = $sth->fetchrow_hashref;
    # quit now if there's no member record
    $parse_hash->{new_member} = 1;
    return undef if(not defined($h));
    $parse_hash->{new_member} = 0;
    return $h;
}

# set up the hash for html output
sub load_parse_hash {
    my ($vals, $config, $cgi, $dbh) = @_;
    map {$vars_2_db{$db_2_vars{$_}}=$_} keys(%db_2_vars);

    my $sth;
    my $h;
    my %parse_hash;
    my %val_hash;
    
    # prepare the hash for the template parsing with empty inputs
    foreach my $k (keys(%inputs)) {
	$parse_hash{$k} = "";
    }

    # get the existing member data
    $h = get_member_data(\%parse_hash, $vals, $dbh);
    return \%parse_hash if(not defined($h));
    $parse_hash{new_member} = 0;

    # fill parse_hash from the database, convert checkbox items
    # to "CHECKED" or ""
    foreach my $k (keys %{$h}) {
	# skip things not fetchable from database
	my $newk = $db_2_vars{$k};
	next if(not defined($newk) or not defined($inputs{$newk}) or
		not defined($inputs{$newk}->{typ}));
	if($inputs{$newk}->{typ} eq "check") {
	    $parse_hash{$newk} = ($h->{$k}) ? "CHECKED" : "";
	} else {
	    $parse_hash{$newk} = escapeHTML($h->{$k});
	}
	# set up sql so we can write it back
	$sql{$k} = $h->{$k};
    }

    return \%parse_hash;
}

# get the form variables and update the parse hash where there is 
# valid data, Accumulates some error messages
# $required determines if empty input fields are relevant
# the values are also placed in the sql hash used to generate update and inserts

sub get_vars {
    my ($required, $vals, $config, $cgi, $dbh) = @_;
    my $parse_hash = load_parse_hash($vals, $config, $cgi, $dbh);
    my $new_val;
    my $res;

    if(not $config->{is_admin}) {
	$vals->{mem} = $mem_id;
	delete($vals->{Admin}) if(defined($vals->{Admin}));
	delete($vals->{Spclacct}) if(defined($vals->{Spclacct}));
    }

    # cycle through all the known input fields
    foreach my $k (keys %inputs) {
	next if(not defined($inputs{$k}->{typ}));
	# and see if the user supplied them
	if(defined($vals->{$k})) {
	    # user supplied input, check it for validity
	    my $v = trimstr($k, $vals);
	    my $typ = $inputs{$k}->{typ};
	    if($typ eq "text") {
		if($v eq "" and $inputs{$k}->{req} and $required) {
		    $err_msgs .= "<p>$inputs{$k}->{desc} can not be blank</p>";
		    $input_err = 1;
		    next;
		}
		# raw input for database
		$sql{$vars_2_db{$k}} = $v;
		# cleansed for html display
		$parse_hash->{$k} = escapeHTML($v);
		next;
	    }

	    if($typ eq "email") {
		$res = get_email($v, \$new_val);
		next if($res == 0 and not $required);
		if($res < 0) {
		    $err_msgs .= 
			"<p>This does not appear to be a vaid email address</p>";
		    $input_err = 1;
		    next;
		}

		$parse_hash->{$k} = escapeHTML($new_val);
		$sql{$vars_2_db{$k}} = $new_val;
		next;
	    }

	    if($typ eq "num") {
		next if($v eq "" and not $required);
		if($v !~ /^\d+/) {
		    $err_msgs .= "<p>$inputs{$k}->{desc} must consist only of digits</p>";
		    $input_err = 1;
		    next;
		}
		$parse_hash->{$k} = escapeHTML($v);
		$sql{$vars_2_db{$k}} = $v;
		next;
	    }

	    if($typ eq "postcode") {
		my $res = get_postcode($vals, \$new_val);
		next if($res == 0 and not $required);
		if($res < 1) {
		    $err_msgs .= "<p>This does not look like a postcode</p>";
		    $input_err = 1;
		    next;
		}

		$parse_hash->{$k} = escapeHTML($new_val);
		$sql{$vars_2_db{$k}} = $new_val;
		next;
	    }

	    if($typ eq "bankacct") {
		$res = get_account_no($v, \$new_val);
		next if($res == 0 and not $required);
		if($res == 0) {
		    $err_msgs .= "<p>A bank account number is required</p>";
		    $input_err = 1;
		    next;
		} elsif($res < 0) {
		    $input_err = 1;
		    if($res == -1) {
			$err_msgs .= "<p>A $inputs{$k}->{desc} must contain only digits</p>";
		    } else {
			$err_msgs .= "<p>This is not a valid $inputs{$k}->{desc}</p>";
		    }

		    next;
		}

		$err_msgs .= "<p>This is a Postbank account number, I hope that is correct</p>"
		    if($res == 1);

		$parse_hash->{$k} = escapeHTML($new_val);
		$sql{$vars_2_db{$k}} = $new_val;
		next;
	    }

	    if($typ eq "telno") {
		$res = telno($v, \$new_val);

		next if($res == 0 and not $required);
		if ($res < 0) {
		    $err_msgs .= "<p>The $inputs{$k}->{desc} is outside the Netherlands</p>" 
			if($res == -1);
		    $err_msgs .= "<p>The $inputs{$k}->{desc} has an unrecognised dialing code</p>" 
			if($res == -4);
		    $err_msgs .= "<p>Please enter the $inputs{$k}->{desc} in the form (0xx) xxx xx xx"
			if($res == -2);
		    $err_msgs .= "The $inputs{$k}->{desc} is the wrong length for a telephone number</p>"
			if($res == -3 or $res == -5); 
		    $input_err = 1;
		    next;
		}
		$parse_hash->{$k} = escapeHTML($new_val);
		$sql{$vars_2_db{$k}} = $new_val;
		next;
	    }

	    if($typ eq "pwd0") {
		next if($v eq "");
		if(!defined($vals->{"Pwd1"})) {
		    $input_err = 1;
		    $err_msgs .= "<p>You did not re-enter your Password</p>";
		}

		my $retype = trimstr("Pwd1", $vals);
		if(length($v) < 6 or length($v) > 30) {
		    $input_err = 1;
                    $err_msgs .= "<p>Passwords must be between 6 and 30 characters long and may not begin or end with spaces</p>";
		    next;
		}
		if($v ne $retype) {
		    $input_err = 1;
		    $err_msgs .= "<p>Passwords do not match</p>";
		    next;
		}
		$sql{mem_enc_pwd} = unix_md5_crypt($v);
		next;
	    }

	    if($typ eq "check") {
		$sql{$vars_2_db{$k}} = 1;
		$parse_hash->{$k} = "CHECKED";
	    }
	}
    }

    return $parse_hash;
}

# fill parse hash from a member row

sub parse_from_member {
    my ($h, $parse_hash) = @_;

    # fill the parser hash from the database, convert checkbox items
    # to "CHECKED"/""
    foreach my $k (keys %{$h}) {
	if(defined($db_2_vars{$k})) {
	    my $newk = $db_2_vars{$k};
	    if(defined($inputs{$newk}->{typ})) {
		if($inputs{$newk}->{typ} eq "check") {
		    $parse_hash->{$newk} = ($h->{$k}) ? "CHECKED" : "";
		} else {
		    $parse_hash->{$newk} = escapeHTML($h->{$k});
		}
		# we will write it back
		$sql{$k} = $h->{$k};
	    }
	}
    }
    $parse_hash->{member_id} = $parse_hash->{Member} = $h->{mem_id};
}

# put up the initial html
sub pass0 {
    my ($vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  hidden      => "edit_member/mem-hidden.template",
	);
    my %h =(  Pagename    => "Select Member to Edit",
	      Title       => "Select Member to Edit",
	      Nextcgi     => "edit_member.cgi",
	      mem_name    => $config->{mem_name},
	      pass        => 1,
	      member_id   => 0,
	      Member      => "",
	      Forename    => "",
	      Lastname    => "",
	      Email       => "",
	);

    $tpl->assign(\%h);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    if(length($err_msgs) > 0) {
    	print "<span class=\"warn\"><big>$err_msgs</big></span>";
    }

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->assign(\%h);
    $tpl->define( main   => "edit_member/mem-admsel.template",
		  footer => "edit_member/mem-pass0.template");
    $tpl->assign(Create => "Create a New Account");
    #$tpl->parse(FOOTER => "footer");
    $tpl->parse(MAIN => "main");
    $tpl->print("MAIN");
    $dbh->commit;
    $dbh->disconnect;
    exit 0;

}

# we come here when it's an admin and they've filled in some selection criteria
sub pass1 {
    my ($vals, $config, $cgi, $dbh) = @_;
    my $parse_hash = get_vars(0, $vals, $config, $cgi, $dbh);

    if((defined($vals->{Member}) and $vals->{Member} ne "") and
       defined($vals->{Create})) {
	$err_msgs .= "<p/>You can't select the member number for a new account, the database will select the number</p>";
	pass0($vals, $config, $cgi, $dbh);
    }

    # see if we can identify who is wanted from the input
    my $sel_cnt = 0;
    my @execvals;
    my $st = "FROM members";

    # ignore other info if member number given
    if(defined($vals->{Member}) and $vals->{Member} =~ /^\s*\d+\s*$/) {
	delete $vals->{Email} if(defined($vals->{Email}));
	delete $vals->{Lastname} if(defined($vals->{Lastname}));
	delete $vals->{Forename} if(defined($vals->{Forename}));
	$vals->{mem} = $vals->{Member};
    }

    # look for the following input terms, count all non-blank entries
    foreach my $k (qw(Forename Lastname Email Member)) {
	if(defined($vals->{$k})) {
	    my $v = trimstr($k, $vals);
	    next if($v eq "");
	    $parse_hash->{$k} = escapeHTML($v);
	    if($k =~ /name/) {
		$v = "\%$v%";
		if($sel_cnt) {
		    $st .= " AND $vars_2_db{$k} ilike ?";
		} else {
		    $st .= " WHERE $vars_2_db{$k} ilike ?";
		}
	    }else {
		if($sel_cnt) {
		    $st .= " AND $vars_2_db{$k} = ?";
		} else {
		    $st .= " WHERE $vars_2_db{$k} = ?";
		}
	    }
	    push @execvals, $v;
	    $sel_cnt++;
	}
    }
    if (defined($vals->{'OnlyActive'})) {
        if ($sel_cnt) {
            $st .= " AND mem_active = true";
        } else {
            $st .= " WHERE mem_active = true";
        }
    }
    
    if($sel_cnt == 0) {
       pass3(5, $parse_hash, $vals, $config, $cgi, $dbh) 
	   if(defined($vals->{Create}));;
    }

    my $cmd = "SELECT count(*) $st";
    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute(@execvals);
    };

    my $aref;
    if(! $@ ) {
	$aref = $sth->fetchrow_arrayref;
	$sth->finish;
    }

    if($@ or not defined($aref) or $aref->[0] == 0) {
	if(not $config->{is_admin}) {
	    pass0($vals, $config, $cgi, $dbh);
	}
	if(defined($vals->{Create})) {
	    pass3(5, $parse_hash, $vals, $config, $cgi, $dbh);
	}
	$err_msgs .= "<p>No member matches your selection</p>";
	pass0($vals, $config, $cgi, $dbh);
    }

    $cmd = "SELECT * $st";
    if (defined($vals->{'OrderBy'})) {
        if ($vals->{'OrderBy'} eq 'id'){
            $cmd .= " ORDER BY mem_id";
        } else {
            $cmd .= " ORDER BY lower(mem_lname), lower(mem_fname), lower(mem_prefix)";
        }
    }

    $sth = prepare($cmd, $dbh);
    $sth->execute(@execvals);
    my $href;
    if($aref->[0] == 1) {
	$href = $sth->fetchrow_hashref;
	$sth->finish;
	$dbh->commit;
	parse_from_member($href, $parse_hash);
	$parse_hash->{new_member} = 0;
	# there's a single match, but we want to make a new member
	if(defined($vals->{Create})) {
	    $err_msgs .= "<p>There is a member who seems to match your specification</p>";
	    pass3(5, $parse_hash, $vals, $config, $cgi, $dbh);
	}
	# we have a match, we aren't trying to create a new one
	$vals->{mem} = $href->{mem_id};
	pass3(4, $parse_hash, $vals, $config, $cgi, $dbh);
    }
    if(not $config->{is_admin}) {
	pass0($vals, $config, $cgi, $dbh);
    }

    # we have more than one match, present matching rows
    $err_msgs .= "<p>Found $aref->[0] members.</p>";
    pass6($sth, $parse_hash, $vals, $config, $cgi, $dbh);

}

# output the html and set the following pass. Used to begin an edit/create 
# phase. Never entered from a submit
sub pass3 {
    my ($next_pass, $parse_hash, $vals, $config, $cgi, $dbh) = @_;

    $parse_hash->{pass} = $next_pass;
    display_pass3($next_pass, $parse_hash, $vals, $config, $cgi, $dbh);
}

sub display_pass3 {
    my ($next_pass, $parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  hidden      => "edit_member/mem-hidden.template",
		  name_tmp    => "edit_member/mem-name.template",
		  addr_tmp    => "edit_member/mem-address.template",
		  phone_tmp   => "edit_member/mem-phone.template",
		  bank_tmp    => "edit_member/mem-bankno.template",
		  pwd_tmp     => "edit_member/mem-passwd.template",
		  adm_tmp     => "edit_member/mem-admin.template",
		  admbut_tmp  => "edit_member/mem-admbuttons.template",
	);
    my %hdr_h =(  Pagename    => "Edit Member Details",
		  Title       => "Edit Member Details",
		  Nextcgi     => "edit_member.cgi",
		  mem_name    => $config->{mem_name},
		  pass        => $next_pass,
		  member_id   => ((defined($vals->{mem})) ? $vals->{mem} : 0),
	);

    $tpl->assign(\%hdr_h);
    $tpl->assign($parse_hash);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    if(length($err_msgs) > 0) {
	print "<span class=\"warn\"><big>$err_msgs</big></span>";
    }
    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  name_tmp    => "edit_member/mem-name.template",
		  addr_tmp    => "edit_member/mem-address.template",
		  phone_tmp   => "edit_member/mem-phone.template",
		  bank_tmp    => "edit_member/mem-bankno.template",
		  pwd_tmp     => "edit_member/mem-passwd.template",
		  adm_tmp     => "edit_member/mem-admin.template",
		  admbut_tmp  => (($next_pass == 4) ?
		  "edit_member/mem-pass4.template" : "edit_member/mem-pass5.template"),
		  membut_tmp  => "edit_member/mem-membuttons.template",
	);
    
    $tpl->assign($parse_hash);

    if($config->{is_admin}) {
	$tpl->parse(ADMBUTTONS => "admbut_tmp");
	if(defined($vals->{mem}) and
	   $mem_id == $vals->{mem}) {
	    $tpl->parse(ADMIN => "adm_tmp");
	    $tpl->parse(PASSWORD => "pwd_tmp");
	} else {
	    $tpl->parse(PASSWORD => "adm_tmp");
	}
    } else {
	$tpl->parse(ADMIN => "membut_tmp");
	$tpl->parse(PASSWORD => "pwd_tmp");
    }
    $tpl->parse(BANKNO => "bank_tmp");
    
    $tpl->parse(PHONE => "phone_tmp");
    $tpl->parse(ADDRESS => "addr_tmp");
    $tpl->parse(MAIN => "name_tmp");
    $tpl->print("MAIN");
    $dbh->disconnect;
    exit 0;
}

# take submitted values and attempt to update an existing record
sub pass4 {
    my ($vals, $config, $cgi, $dbh) = @_;

    my $parse_hash = get_vars(1, $vals, $config, $cgi, $dbh);
    if(not $config->{is_admin}) {
	del $sql{mem_admin};
	del $sql{mem_membership_paid};
	del $parse_hash->{Admin};
	del $sql{mem_active};
	del $parse_hash->{Active};
	del $sql{mem_adm_adj};
	del $parse_hash->{Spclacct};
    } else {
	if(not defined($vals->{Mem_Paid})) {
	    $sql{mem_membership_paid} = 0;
	    $parse_hash->{Mem_Paid} = "";
	}
	if(not defined($vals->{Admin})) {
	    $sql{mem_admin} = 0;
	    $parse_hash->{Admin} = "";
	}
	if(not defined($vals->{Active})) {
	    $sql{mem_active} = 0;
	    $parse_hash->{Active} = "";
	}
	if(not defined($vals->{Spclacct})) {
	    $sql{mem_adm_adj} = 0;
	    $parse_hash->{Spclacct} = "";
	}
    }
    my @not_null = qw(mem_fname mem_lname mem_street mem_house mem_postcode mem_enc_pwd mem_email);

    # we shouldn't come here on create account, but just to be sure...
    return pass5($vals, $config, $cgi, $dbh) if ($parse_hash->{new_member});
    $parse_hash->{passno}= 3;

    if(! $input_err) {
	# no input to work with - should never happen
	return $parse_hash if(scalar(keys %sql) < 1);
	$sql{mem_message_auth} = $mem_id;

	# generate an update statment. @sql_set will be an array of the
	# keys in %sql, @execvals will be the values in %sql in the same
	# order
	my @sql_set =  map "$_ = ?", keys(%sql);
	my @execvals = map $sql{$_}, keys(%sql);
	# the very last parameter needed is the mem_id
	push @execvals, $vals->{mem};
	my $cmd =  sprintf("UPDATE members SET %s WHERE mem_id = ?", 
			   join ", ", @sql_set);

	my $sql_ref = \%sql;
	my $sth = prepare($cmd, $dbh);
	eval {
	    $sth->execute(@execvals);
	};
	if($@) {
	    $err_msgs .= $@;
	    $dbh->rollback;
	} else {
	    $err_msgs = "<p>Member Account Updated</p>";
	    $dbh->commit;
	    if($config->{is_admin} and (not defined($vals->{Active}) or not $vals->{Active}) 
	       and $status < 4) {
		$sth = prepare(
		    "SELECT remove_inactive_member_order(?)", $dbh);
		$sth->execute($vals->{mem});
		$dbh->commit;
	    }
	    if(defined($vals->{SendEmail})) {
		password_reset($vals->{mem}, $parse_hash->{Email}, 3, 
			       $config, $dbh);
	    }
	    # reload with the new values - should be the same, but...
	    $parse_hash = load_parse_hash($vals, $config, $cgi, $dbh);
	}
    }
    display_pass3(4, $parse_hash, $vals, $config, $cgi, $dbh);

}

# take submitted values and try to insert a new record	
sub pass5 {
    my ($vals, $config, $cgi, $dbh) = @_;
    my $parse_hash = get_vars(1, $vals, $config, $cgi, $dbh);
    my @not_null = qw(mem_fname mem_lname mem_street mem_house mem_postcode mem_email mem_bank_no);
    
    # we shouldn't come here on edit account, but just to be sure...
    return pass4($vals, $config, $cgi, $dbh) if (not $parse_hash->{new_member});
    $parse_hash->{passno}= 5;

    if(! $input_err) {
	# we're creating a member, have we got everything?
	foreach my $col (@not_null) {
	    if(not defined($sql{$col})) {
		if(defined($db_2_vars{$col})) {
		    $err_msgs .= "<p>Must have a value for $inputs{$db_2_vars{$col}}->{desc} must have a value before member can be created</p>";
		} else {
		    $err_msgs .= "<p>You must supply a starting password</p>";
		}
			   
		$input_err = 1;
	    }
	}
	my $sql_keys = join ", ", @not_null;
	my @qms = map "?", @not_null;
	my @execvals = map $sql{$_}, @not_null;

	my $has_pn = 0;
	foreach my $pn (qw(mem_home_tel mem_mobile mem_work_tel)) {
	    if(defined($sql{$pn}) and length($sql{$pn}) >= 7) {
		$has_pn = 1;
		$sql_keys = sprintf("%s %s", $sql_keys, (length($sql_keys) == 0) ?  $pn : ", $pn");
		push @qms, "?";
		push @execvals, $sql{$pn};
	    }
	}

	if(! $has_pn) {
	    $err_msgs .= "<p>You must supply at least one telephone number</p>";
	    $input_err = 1;
	}
	display_pass3(5, $parse_hash, $vals, $config, $cgi, $dbh)
	    if($input_err);

	# generate a big random number and make it the initial 
	# password (new member will have to set a real password, 
	open(RND, "</dev/random");
	my $buf;
	sysread RND, $buf, 18;
	close(RND);
	my $key = encode_base64($buf);
	chomp $key;
	$sql{mem_enc_pwd} = $key;
	push @execvals, $key;
	push @qms, "?";
	# add date/time and admin mem_id (for messages)
	# a trigger in the database will decide if these are used 
	# or not 
	$sql{mem_message_auth} = $config->{mem_id};
	push @execvals, $config->{mem_id};
	push @qms, "?";

	$sql_keys = sprintf("%s %s", $sql_keys, (length($sql_keys) == 0) ?  
			    "  mem_enc_pwd, mem_message_auth":
			    ", mem_enc_pwd, mem_message_auth");

	my $cmd = sprintf("INSERT INTO members (%s) VALUES (%s)", 
			  $sql_keys, 
			  join(", ", @qms));
	my $sth;
	my $sqlref = \%sql;
	$sth = prepare($cmd, $dbh);
	eval {
	    $sth->execute(@execvals);
	};

	if($@) {
	    $err_msgs = "Insert failed $@";
	    $dbh->rollback;
	} else {
	    $err_msgs = "<p>Member Account Created</p>";
	    $sth = prepare("SELECT currval('members_mem_id_seq')", $dbh);
	    $sth->execute();
	    my $aref = $sth->fetchrow_arrayref;
	    $vals->{mem} = $aref->[0];
	    $dbh->commit;
	    password_reset($vals->{mem}, $parse_hash->{Email}, 35, 
			   $config, $dbh);
	    $parse_hash = load_parse_hash($vals, $config, $cgi, $dbh);	
	    display_pass3(4, $parse_hash, $vals, $config, $cgi, $dbh);
	}
    }
    display_pass3(5, $parse_hash, $vals, $config, $cgi, $dbh);
}

# come here with an active handle for multiple matches
sub pass6 {
    my ($sth, $parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  hidden      => "edit_member/mem-hidden.template",
	);
    my %hdr_h =(  Pagename    => "Edit Member Details",
		  Title       => "Edit Member Details",
		  Nextcgi     => "edit_member.cgi",
		  mem_name    => $config->{mem_name},
		  pass        => 7,
		  member_id   => 0,
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    #if(length($err_msgs) > 0) {
    #	print "<span class=\"warn\"><big>$err_msgs</big></span>";
    #}

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "edit_member/mem-rowhder.template",
		  row         => "edit_member/mem-rows.template",
		  footer      => "edit_member/mem-rowftr.template");
    my %hdr =(    err_msgs     => $err_msgs,
		  pass         => 7,
		  mem          => 0,

		  );
    $tpl->assign(\%hdr);
    $tpl->parse(FOOTER => "footer");
    my $Selected = "CHECKED";
    while(my $href = $sth->fetchrow_hashref) {
	$tpl->assign({
	    mem_id       => $href->{mem_id},
	    mem_fname    => escapeHTML($href->{mem_fname}), 
	    mem_prefix   => escapeHTML($href->{mem_prefix}),
	    mem_lname    => escapeHTML($href->{mem_lname}), 
	    mem_email    => escapeHTML($href->{mem_email}),
	    mem_street   => escapeHTML($href->{mem_street}),
	    mem_house    => escapeHTML($href->{mem_house}),
	    mem_flatno   => escapeHTML($href->{mem_flatno}),
	    mem_postcode => escapeHTML($href->{mem_postcode}),
	    Selected     => $Selected,
		     });

	$tpl->parse(ROWS => ".row");
	$tpl->clear_href(1);
	$Selected = "";
    }
    $sth->finish;
    $dbh->commit;
    $tpl->parse(TABLE => "header");
    $tpl->print("TABLE");
    exit 0;
}

# pass7 - come here after selecting a row
# will either go to pass 4 (edit existing row
# or pass 5 - create a new member
sub pass7 {
    my ($vals, $config, $cgi, $dbh) = @_;
    my $parse_hash;

    pass0($vals, $config, $cgi, $dbh) if(!defined($vals->{selected_row}));
    if(defined($vals->{Edit})) {
	my $v = $vals->{selected_row};
	pass0($vals, $config, $cgi, $dbh) if($v !~ /^m_(\d+)$/);
	$vals->{mem} = $1;
	$parse_hash = load_parse_hash($vals, $config, $cgi, $dbh);
	pass3(4, $parse_hash, $vals, $config, $cgi, $dbh);
    }
    # prepare the hash for the template parsing with empty inputs
    foreach my $k (keys(%inputs)) {
	$parse_hash->{$k} = "";
    }

	
    pass3(5, $parse_hash, $vals, $config, $cgi, $dbh);
}

my @dispatch = (
    \&pass0, \&pass1, \&pass2, \&pass0,
    \&pass4, \&pass5, \&pass0, \&pass7,
    );

sub doit {
    my ($vals, $config, $cgi, $dbh) = @_;

    my $pass = (defined($vals->{pass})) ? int($vals->{pass}) : 0;
    $pass = 0 if($pass < 0 or $pass > 7);
    my @args = ($vals, $config, $cgi, $dbh);
    my $sub = $dispatch[$pass];
    &$sub($vals, $config, $cgi, $dbh);
}
    
sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);
    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;
    openlog( $program, LOG_PID, LOG_USER );

    # verify config is complete
    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	$mem_id = process_login(0, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(0, $config, $cgi, $dbh);
    }

    my $vals = $cgi->Vars;
    #dump_stuff("edit_member", "main", "vars", $vals);
    if(not $config->{is_admin}) {
	$vals->{mem} = $vals->{Member} = $mem_id;
	$vals->{pass} = "1" if(not defined($vals->{pass}));
    }
    doit($vals, $config, $cgi, $dbh);


}
main;
