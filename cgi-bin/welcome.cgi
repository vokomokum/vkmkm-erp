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
my $config;
my $order_name = "";

sub print_html {
    my ($config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  news        => "../data/news/newsletter",
	);
    my %hdr_h =(  Pagename    => "Welcome to Vokomokum",
		  Title       => "Welcome to Vokomokum",
		  Nextcgi     => '/cgi-bin/mem_order.cgi',
		  mem_name    => $config->{mem_name},
		  order_name  => $order_name,
		  BUTTONS     => "",
	);


    $hdr_h{BANNER} = '    <p align="center"><a href="/cgi-bin/mem_order.cgi">[Login]</a></p>' . "\n"
	if(not defined($config->{mem_name}) or $config->{mem_name} eq '');
    $tpl->assign(\%hdr_h);
    
    admin_banner($status, "BANNER", "banner", $tpl, $config) 
	if(defined($config->{mem_name}) and $config->{mem_name} ne '');
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    $tpl->parse(NEWS => "news");
    $tpl->print("NEWS");
    print <<EOF
</form>
</body>
</html>
EOF
;

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
    ($status, $ord_no, $order_name) = ($config->{status}, $config->{ord_no},
				       $config->{ord_label});

    # if we have a cookie, get the name but don't force a login
    if(($mem_id = process_login_data(0, $config, $cgi, $dbh)) < 0) {
	
	$mem_id = test_cookie(0, $config, $cgi, $dbh);
    }
	    

    syslog(LOG_ERR, "welcome - >$mem_id<");
    print_html($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
