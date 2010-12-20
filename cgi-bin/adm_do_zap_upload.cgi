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
my $datadir = "../zapatistadata";
my $datafile = "newdata";
my $mem_id;
my $ord_no;
my $status;
my $err_msgs = "";
my $config;
my $order_name = "";

#bestelnr	omschriving	aantal	inkoopprijs	btw	url

#spreadsheet
#1	rebeldia (espresso) [Café Libertad] 250gr	1	4,36	6
# http://www.cafe-libertad.de/shop/kaffee/espresso/bio-espresso-rebeldia-250g-gemahlen.html

# create a hash of column number to column name
sub make_col_hash {
    my ($fh, $zap) = @_;
    my $line;

    while($line = <$fh>) {
	$line =~ s/\s+$//;
        next if($line =~ /^$/);
        last if($line !~ /^\#/);
    }

    die("file $zap appears to be empty") if(not defined($line));
    die("$zap does not look like a Zapatista Coffee Product file - no bestelnr column") 
	if($line !~ /^bestelnr\t/);
    my %col_names;
    # trim any cruft off the end
    $line =~ s/\s+$//;
    my $i = 0;
    my @names = split(/\t/, $line);
    die("$zap does not look like a Zapatista Coffee Product file - wrong number of columns")
	if(scalar(@names) != 6);
    map { $col_names{$i++} = $_ } @names;
    return \%col_names;
}

# get the key which identifies the file, to prevent running the same file
# twice. It will also check that the file being run is newer than the 
# old file
sub get_file_key {
    my ($fh, $zap, $config, $dbh) = @_;
    my $line = <$fh>;

    if(not defined($line)) {
	$dbh->disconnect;
	die("file $zap appears to be empty");
    }
    #dump_stuff("make_col_hash", "", "", \$line);

    if($line !~ m@0\t+(\d+)[/-](\d+)[/-](\d+)\s+(\d+):(\d+):(\d+)@) {
	$dbh->disconnect;
	die("$zap does not look like a Zapatista Coffee Product file - missing file's datestamp");
    }
    #dump_stuff("get key", $line, "", [$1, $2, $3, $4, $5, $6]);
    my($yr, $mo, $day, $hr, $min, $sec) = ($1, $2, $3, $4, $5, $6);
    my $newkey ="$yr/$mo/$day $hr:$min:$sec";
    my $sth = prepare(
	'SELECT wh_update FROM wholesaler WHERE wh_id = ?', $dbh);
    $sth->execute($config->{ZAPATISTA}->{zap_wh_id});
    my $h;
    eval {
	$h = $sth->fetchrow_hashref;
	$sth->finish;
    };

    if($dbh->err) {
	my $m = $@;
	$dbh->disconnect;
	die($m);
    }
    return $newkey if(not defined($h->{wh_update}));
    #dump_stuff("getkey", "$newkey", "", {});
    if($newkey eq $h->{wh_update}) {
	$dbh->disconnect;
	die ("This file has already been processed");
    }
    
    if($newkey lt $h->{wh_update}) {
	$dbh->disconnect;
	die("This file is older than the most recently processed one ($h->{wh_update}");  
    }

    return $newkey;
}

sub process {
    my ($config, $cgi, $dbh) = @_;

    my $zap = "$datadir/$datafile";
    die("Can't find a Zapatista Coffee data file $datadir/$datafile")
	if(not -f "$datadir/$datafile");

    my $fh;
    open($fh, "< $zap") or die "Can't open $zap: $!";
    my $cols = make_col_hash($fh, $zap);
    my $newkey = get_file_key($fh, $zap, $config, $dbh);
    my $line = 1;
    
    # get the timestamp we will use
    my %h;
    $newkey =~ /^(.*)\s+(.*)$/;
    my $suffix = $1;
    my $sth = prepare("SELECT (date '$1' + time '$2')", $dbh);
    $sth->execute;
    my $a = $sth->fetchrow_arrayref;
    $sth->finish;
    my $now = $a->[0];
	
    while(<$fh>) {
	++$line;
	s/\s+$//;
	my @data = split(/\t/, $_);
	my $items = scalar(@data);
	next if($items < 2);
	#print "Couldn't parse line $line, skipping it: \n$$_\n" 

	next if($items < 6);
	for(my $i = 0; $i < scalar(@data); ++$i) {
	    $h{$cols->{$i}} = $data[$i];
	}
	$h{bestelnr} = int($h{bestelnr});
	$h{aantal} =~ s/,/./;
	$h{inkoopprijs} =~ s/,/./;
	my $aant = int($h{aantal});
	$h{wh_pri} = int(100 * $aant * $h{inkoopprijs});
	$h{omschrijving} .= " ($aant per wholesale order)";
	$h{btw} =~ s/,/./;
	$sth = prepare("SELECT put_zap(?, " .  # prcode
                                 "?, " .       # descr
                                 "?, " .       # wh_q
                                 "?, " .       # whpri
                                 "?, " .       # btw 
                                 "?, " .       # url
                                 "? )",        # tstamp
		       $dbh);
	    eval {
		$sth->execute( $h{bestelnr},  
			       $h{omschrijving}, 
			       $aant,
			       $h{wh_pri},
			       $h{btw},
			       $h{url},
			       $now);
	    };
	    if($dbh->err) {
		my $m = $@;
		$dbh->rollback;
		$dbh->disconnect;
		die($m);
	    }
    }

    $sth = prepare(
	'UPDATE wholesaler SET wh_update = cast(? as timestamp) WHERE wh_id = ?', $dbh);
    eval {
	$sth->execute($newkey, $config->{ZAPATISTA}->{zap_wh_id});
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->rollback;
	$dbh->disconnect;
	die($m);
    }

    $dbh->commit;
    $suffix =~ s/\///g;
    rename "$datadir/$datafile", "$datadir/zapassor.$suffix.zip";
    return $line;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    
    my $src_fh = $cgi->upload("zap_data_file");
    my $tf = "$datadir/$datafile";
    my $tgt_fh;
    my $raw_fh;

    open($tgt_fh, ">$tf") or die "Can't open $tf: $!"; 
    while(my $l = <$src_fh>) {
	#dump_stuff("doit", $l, "", \$src_fh);
	print $tgt_fh $l;
    }
    
    close($tgt_fh);
    close($src_fh);

    my $count = process($config, $cgi, $dbh);

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    my $buttons = {}; # 
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  buttons        => "adm_zap/adm_zap_file_done.template",
	);
    my %hdr_h =(  Pagename       => 'Zapatista Coffee File Processing Complete',
		  Title          => 'Zapatista Coffee File Processing Complete',
		  Nextcgi        => 'adm_zap.cgi',
		  mem_name       => $config->{mem_name},
		  count          => $count,
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print '</form></body></html>';
    exit 0;


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
