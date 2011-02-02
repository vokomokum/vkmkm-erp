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
my $err_msgs = "";
my $config;


sub print_html {
    my ($cgi, $dbh) = @_;
    

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "logout/logout_banner.template",
	);
    my %hdr_h =(  Pagename    => 'Goodbye',
		  Title       => 'Goodbye',
		  Nextcgi     => '/cgi-bin/mem-login',
		  );


    $tpl->parse(BANNER => "banner");
    $tpl->assign(\%hdr_h);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
}

sub doit {
    my ($cgi, $dbh) = @_;
    syslog(LOG_ERR, "remove cookie for $mem_id");
    my $sth = prepare('UPDATE members SET mem_cookie = NULL WHERE mem_id = ?', $dbh);
    $sth->execute($mem_id);
    $sth->finish;
    $dbh->commit;
    print_html($cgi, $dbh);
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
    if($program =~ /login/) {
	$mem_id = process_login(0, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(0, $config, $cgi, $dbh);
    }

    doit($cgi, $dbh);

	$dbh->disconnect;
    exit 0;

}
main;
