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
my $err_msgs = "";
my $is_error = 0;
my $config;

my %inputs = (Member   => "no_or_email",
	      Phone    => "telno",
	      House    => "num",
	      Postcode => "postcode",
	      key      => "key",
	      pass     => "num",
	      Pwd0     => "pwd",
    );

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


sub get_postcode {
    my ($pc, $where ) = @_;

    return -1 if($pc !~ /^\s*(\d\d\d\d)\s*([a-z][a-z])\s*$/i);
    $$where = sprintf "%s %s", $1, uc $2;
    return 1;
}
sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my %parse_hash;
    my $missing = 0;
    my $req = defined($vals->{pass});
    my $new_val;
    my $res;

    foreach my $k (keys %inputs) {
	if(not defined($vals->{$k})) {
	    $parse_hash{$k} = "";
	    $missing = 1;
	    next;
	}
	my $v = $vals->{$k};
	$v =~ s/^\s*//;
	$v =~ s/\s+$//;
	$parse_hash{$k} = $v;
	if($v eq "") {
	    $missing = 1;
	    next;
	}

	if($inputs{$k} eq "no_or_email") {
	    if($v =~ /^\d+$/) {
		$parse_hash{mem_id} = $v;
		next;
	    }

	    $res = get_email($v, \$new_val);
	    if($res < 0 and $req) {
		$missing = 1;
		$err_msgs .= '<div class="warn">This does not look like a valid email address</div>';
		next;
	    }
	    $parse_hash{$k} = $parse_hash{$k} = $new_val;
	    next;
	}

	if($inputs{$k} eq "num") {
	    next if($v =~ /^\d+$/);
	    $missing = 1;
	    $err_msgs .= '<div class="warn">House number must contain only digts</div>'
		if($req);
	    next;
	}

	if($inputs{$k} eq "telno") {
	    $res = telno($v, \$new_val);
	
	    if($res == 1) {
		$parse_hash{$k} = escapeHTML($new_val);
		next;
	    }

	    $missing = 1;
	    $err_msgs .= '<div class="warn">The phone number is outside the Netherlands</div>'
		if($res == -1);
	    $err_msgs .= '<div class="warn">Please enter the phone number in the form (0xx) xxx xx xx</div>'
		if($res == -2);
	    $err_msgs .= '<div class="warn">The phone number is the wrong length</div>'
		if($res == -3 or $res == -5); 
	    $err_msgs .= '<div class="warn">The phone number has an unrecognised dialing code</div>' 
		if($res == -4);

	    next;
	}

	if($inputs{$k} eq "postcode") {
	    $res = get_postcode($v, \$new_val);
	    if($res > 0) {
		$parse_hash{$k} = $new_val;
		next;
	    }
	    $missing = 1;
	    $err_msgs .= '<div class="warn">This does not look like a valid postcode</div>'
		if($req);
	    next;
	}
	
	if($inputs{$k} eq "pwd") {
	
	    if(!defined($vals->{"Pwd1"})) {
		$missing = 1;
		$err_msgs .= '<div class="warn">You did not re-enter your Password</div>'
		    if($req);
	    }

	    my $retype = $vals->{Pwd1};
	    $retype =~ s/^\s*//;
	    $retype =~ s/\s+$//;
	    if(length($v) < 6 or length($v) > 30) {
		$missing = 1;
		$err_msgs .= '<div class="warn">Passwords must be between 6 and 30 characters long and may not begin or end with spaces</div>';
		next;
	    }
	    if($v ne $retype) {
		$missing = 1;
		$err_msgs .= '<div class="warn">Passwords do not match</div>';
		next;
	    }
	    $parse_hash{pwd} = $v;
	    next;
	    
	}
	
    }
    $is_error = 1 if($missing and $req);
    return \%parse_hash if(not $req or $missing);

    # try to find a matching member record
    my $cmd = sprintf "SELECT * FROM members WHERE %s = ? AND mem_house = ? " .
	"AND mem_postcode = ?", (defined($parse_hash{mem_id})) ? 
	'mem_id' : 'mem_email';
    my @execvals =  (defined($parse_hash{mem_id})) ?
        ($parse_hash{mem_id}) : ($parse_hash{Member});
    push @execvals, $parse_hash{House}, $parse_hash{Postcode};
    my $sth = prepare($cmd, $dbh);
    $sth->execute(@execvals);
    my $href = $sth->fetchrow_hashref;
    $sth->finish;
    $is_error = 1;

    if(not defined($href)) {
	$err_msgs .= '<div class="warn">Could not find an account matching these details</div>';
    }
    while ( defined( $href ) ) {
        # is the phone no on record?
        foreach my $k ( qw( mem_home_tel mem_mobile mem_work_tel ) ) {
            if ( $parse_hash{Phone} eq $href->{$k} ) {
                $is_error = 0;
                last;
            }
        }
	
    	if ( $is_error ) {
    	    $err_msgs .= '<div class="warn">You must supply a telephone number</div>';
    	    last;
    	}
	
        $is_error = 1;
    	if ( not defined( $href->{mem_pwd_url} ) ) {
            $err_msgs .= '<div class="warn">This page is invalid for this account or has expired</div>';
    	    last;
    	}
    	
    	if ( $href->{mem_pwd_url} !~ /^([^:]*):(\d+)$/ ) {
    	    $err_msgs .= '<div class="warn">This page is not valid for this account or has expired</div>';
    	    last;
    	}
 	
        my ($url, $tstamp) = ($1, $2);
        # arrgh a plus sign becomes a space after going through processing
        $url =~ s/\+/ /g;
        if ( $url ne $vals->{key} ) {
            $err_msgs .= '<div class="warn">This page is invalid for this account or has expired</div>';
            last;
        }
        
    	if ( ( $tstamp - time ) < 0 ) {
	    $err_msgs .= '<div class="warn">This page is not valid for this account or has expired</div>';
    	    last;
    	}
    	
    	$is_error = 0;
    	last;
    	
    }
    $parse_hash{mem_id} = $href->{mem_id} if ( not $is_error );
    return \%parse_hash;
    
}

    
# initial page
sub pass0 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;
    $dbh->disconnect;
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  info        => "forgot/forgot0.template",
	);

    my %hdr_h =(  Pagename    => "Reset My Password",
		  Title       => "Reset My Password",
		  Nextcgi     => 
		  escapeHTML("/cgi-bin/forgot.cgi?key=$vals->{key}"),
		  Member      => $parse_hash->{Member},
		  House       => $parse_hash->{House},
		  Postcode    => $parse_hash->{Postcode},
		  Phone       => $parse_hash->{Phone},
		  Postcode    => $parse_hash->{Postcode},
		  key         => $parse_hash->{key},
		  mem_id      => ((defined($parse_hash->{mem_id})) ?
		  $parse_hash->{mem_id} : 0),
		  pass        => 1,
		  err_msgs    => $err_msgs,
		  BANNER      => "",
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    
    if ( $is_error and $err_msgs ne "" ) {
	   #print "<span class=\"warn\"><big>$err_msgs</big></span>";
    }
    
    $tpl->parse(BODY => "info");
    $tpl->print("BODY");
    exit(0);
}

# come here after data is filled in. 
sub pass1 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass0($parse_hash, $vals, $config, $cgi, $dbh) if($is_error);
    # we have a member id and a password
    # update the account

    set_cookie($parse_hash->{mem_id}, $config, $cgi, $dbh);
    my $enc = unix_md5_crypt($vals->{Pwd0});
    my $cmd = "UPDATE members SET mem_enc_pwd = ?, mem_pwd_url = '' " .
	" WHERE mem_id = ?";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($enc, $parse_hash->{mem_id});
    $dbh->commit;
    $dbh->disconnect;
    
    # send them an innocuous page to allow the cookie setting to work
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  info        => "forgot/forgot1.template",
	);

    my %hdr_h =(  Pagename    => "Your Password is Updated",
		  Title       => "Your Password is Updated",
		  Nextcgi     => '/cgi-bin/welcome.cgi',
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BANNER => "info");
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print <<EOF
</form>
</body>
</html>
EOF
;
    exit(0);
}

sub doit {
    my ($config, $cgi, $dbh) =@_;
    my $vals = $cgi->Vars;
    my $parse_hash = get_vars($config, $cgi, $dbh);
    pass0($parse_hash, $vals, $config, $cgi, $dbh) 
	if(not defined($vals->{pass}));
    pass1($parse_hash, $vals, $config, $cgi, $dbh);

    # if pass is weird
    pass0($parse_hash, $vals, $config, $cgi, $dbh);

}

sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    $config = read_conf($conf);
    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;
    openlog( $program, LOG_PID, LOG_USER );

    my ($cgi, $dbh) = open_cgi($config);
    doit($config, $cgi, $dbh);
    $dbh->disconnect;
    exit 0;

}
main;
