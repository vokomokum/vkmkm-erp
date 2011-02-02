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

# recursive remove of colour
# returns string with html escaping, flag to indicate
# that escape needs closing
sub colour_phrase {
    my ($l, $flag) = @_;
    my ($left, $colour, $right);
    my %col = (RED => 'red', BLUE=>'blue', GREEN=>'green',
	       BLACK => 'black');

    while($l =~ /^(.*)(RED|BLUE|GREEN|BLACK)(.*)/) {
	($left, $colour, $right) = ($1, $2, $3);
	($left, $flag) = colour_phrase($left, $flag);
	$left .= '</font>' if($flag);
	$l = $left . "<font color=\"$col{$colour}\">" . $right;
	$flag = 1;
    }
    return ($l, $flag);
}    

sub doit {
    my ($config, $cgi, $dbh) = @_;
    
    my $src_fh = $cgi->upload("welcome");
    my $f = $cgi->param("welcome");
    my $tgt_fh;
    my $raw_fh;
    my $tf = "../news/tmp_newsletter";
    my $rf = "../news/tmp_newsletter.txt";
    open($tgt_fh, ">$tf") or die "Can't open $tf: $!"; 
    open($raw_fh, ">$rf") or die "Can't open $rf: $!";
    my $close_h = "";
    my $font = 0;
    while(my $l = <$src_fh>) {
	# $l =~ s/\r//g;
	print $raw_fh $l;
	$l = escapeHTML($l);
	$l =~ s!UNBOLD!</B>!g;
	$l =~ s!BOLD!<B>!g;
	$l =~ s!FORMAT!</pre>!g;
	$l =~ s!NOFORM!<pre>!g;
	$l =~ s!PARA!<P/>!g;
	($l, $font) = colour_phrase($l, $font) 
	    if($l =~ /^.*RED|BLUE|GREEN|BLACK/);
	while($l =~ qr@(?<![</])(H[123])@) {
	    $l =~ s@^(.*)(?<![</])(H[123])(.*)$@$1<BR><$2 align=\"center\">$3</$2>@;
	}
	while($l =~ qr@(?<![</])(BR)@) {
	    $l =~ s@^(.*)(?<![</])BR(.*)$@$1<BR>$2@;
	}
	print $tgt_fh $l;
    }
    
    close($tgt_fh);
    close($src_fh);
    close($raw_fh);
    
    my $nwl = "../data/news/newsletter";
    my $nwr = "../data/news/newsletter.txt";
    unlink $nwl or die "Can't unlink $nwl: $!" if( -x $nwl);
    unlink $nwr or die "Can't unlink $nwr $!" if(-x $nwr);
    rename $tf, $nwl or die "Can't rename $tf as $nwl: $!";
    rename $rf, $nwr or die "Can't rename $rf as $nwr: $!";
    exec "./welcome.cgi";
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
    $mem_id = test_cookie(0, $config, $cgi, $dbh)
	if(($mem_id = process_login_data(0, $config, $cgi, $dbh)) < 0);

    syslog(LOG_ERR, "welcome - >$mem_id<");

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
