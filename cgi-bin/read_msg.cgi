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
my $status;
my $ord_no;

# do they want to delete the message?
sub get_vars {
    my ($cgi, $config, $dbh) = @_;
    my $vals = $cgi->Vars;

    return if(not defined($vals->{Delete})); 
    # delete any messages
    my $sth = prepare("UPDATE members SET mem_message='' WHERE mem_id = ?", 
		      $dbh);
    eval {
	$sth->execute($mem_id);
    };
    if($@) {
	$dbh->rollback;
    } else {
	$config->{has_message} = 0;
	$dbh->commit;
    }
}


sub doit {
    my ($config, $cgi, $dbh) =@_;
    my $temp;
    my $foot;
    my $h;

    get_vars($cgi, $config, $dbh);
    my $sth = prepare("SELECT * FROM mem_msg WHERE mem_id = ?", $dbh);
    eval {
	$sth->execute($mem_id);
	$h = $sth->fetchrow_hashref;
	$sth->finish();
    };
    if($@ or not defined($h) or $h->{body} eq  "") {
	$h = {};
	$temp = "read_msg/no-message.template";
    } else {
	$temp = "read_msg/message.template";
    }
    
    $config->{title} = "Read Message From Administrators";
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  message     => $temp,
	);

    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => "/cgi-bin/read_msg.cgi",,
		  mem_name    => $config->{mem_name},
		  BUTTONS     => "",
	);
    
    $tpl->assign(\%hdr_h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    my $tpb = new CGI::FastTemplate($config->{templates});
    $tpb->strict();
    $tpb->define( temp => $temp );
    $tpb->assign( $h );
    $tpb->parse("MAIN" => "temp");
    $tpb->print("MAIN");
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
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	$mem_id = process_login(0, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(0, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);
    $dbh->disconnect;
    exit 0;

}
main;
