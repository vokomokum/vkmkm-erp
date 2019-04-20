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
my $datadir    = "../odindata";
my $datafile   = "newdata.zip";
my $md5sum     = "/usr/bin/md5sum";
my $err_msgs   = "";
my $order_name = "";
my $mem_id;
my $ord_no;
my $status;
my $config;

#bestelnummer	omschrijving	btw	inhoud	kassaomschrijving	eenheid	merk	cblcode	sve	verpakkingce	status	inkoopprijs

my $tstamp;

# create a hash of column number to column name
sub make_col_hash {
    my ($fh, $odin) = @_;
    my $line = <$fh>;
    die("file $odin appears to be empty") if(not defined($line));
    
    die("$odin does not look like a Odin product file - no bestelnummer column") 
	if($line !~ /^bestelnummer\t/);
    my %col_names;
    # trim any cruft off the end
    $line =~ s/\s+$//;
    my $i = 0;
    my @names = split(/\t/, $line);
    die("$odin does not look like an Odin product file - not enough columns")
	if(scalar(@names) < 12);
    map { $col_names{$i++} = $_ } @names;
    return \%col_names;
}

my $digest;

# get the md5sum of this file and check that it's not been seen before
sub check_unique_file {
    my ($fh, $odin, $config, $dbh) = @_;
    my $md5fh;
    if(not open($md5fh, "$md5sum $datadir/$datafile |")) {
        $dbh->disconnect;
        die("$md5sum $datadir/$datafile failed: $!");
    }

    $digest = <$md5fh>;
    close($md5fh);
    $digest    =~ s/([a-f0-9]+)\s+.*/$1/;

    my $sth = prepare('SELECT md5sum FROM odin_md5s WHERE md5sum = ?', $dbh);
    my $h;
    eval {
        $sth->execute($digest);
        $h = $sth->fetchrow_hashref;
        $sth->finish;
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->disconnect;
	die ("Can't select from odin_md5s: $m");
    }
    if(defined($h)) {
	die ("This file has already been processed");
    }
    $sth = prepare('INSERT INTO odin_md5s (md5sum, date_seen) VALUES (?, LOCALTIMESTAMP)', $dbh);

    eval {
        $sth->execute($digest);
        $sth->finish;
        $dbh->commit;
        $sth = prepare('SELECT date_seen FROM odin_md5s where md5sum = ?', $dbh);
	$sth->execute($digest);
        $a = $sth->fetchrow_arrayref;
        $tstamp = $a->[0];
        #$tstamp =~ s/\+.*//;
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->disconnect;
	die ("Can't record md5 digest in odin_md5s: $m");
    }
}

sub process {
    my ($config, $cgi, $dbh) = @_;

    my $odin = "$datadir/$datafile";
    die("Can't find an Odin data file $datadir/$datafile")
	if(not -f "$datadir/$datafile");

    my $iconv = $config->{iconv};
    die("Can't find $iconv which is required to convert the text into UTF-8")
	if(not -x $iconv);

    my $infile = "$config->{unzip} -c $odin";
    my $iconv_cmd = "$infile | $iconv --from-code=ISO-8859-1 --to-code=UTF-8 -";
    open(DBD, "$iconv_cmd |") or die "Can't run $iconv_cmd: $!";
    my $fh = *DBD{IO};
    my $junk = <$fh>;
    $junk =  <$fh>;
    my $cols = make_col_hash($fh, $odin);
    check_unique_file($fh, $odin, $config, $dbh);
    my $line = 1;
    my %h;

    while(<$fh>) {
	++$line;
	s/\s+$//;
	my @data = split(/\t/, $_);
	my $items = scalar(@data);
	next if($items < 2);
	#print "Couldn't parse line $line, skipping it: \n$$_\n" 

	next if($items < 12);
	for(my $i = 0; $i < scalar(@data); ++$i) {
	    $h{$cols->{$i}} = $data[$i];
	}
        if($h{status} =~ /Non actief/i) {
            next;
        }
	$h{bestelnummer} =~ s/^\s0*//;
	$h{bestelnummer} = int($h{bestelnummer});
	$h{kassaomschrijving} .= " [$h{merk}]" if($h{merk} ne '');
	$h{sve} =~ s/,/./;
	$h{inhoud} =~ s/,/./;
	$h{inkoopprijs} =~ s/,/./;
	my $aant = $h{sve};
	$h{wh_pri} = int(100 * $aant * $h{inkoopprijs});
	my $inh = $h{inhoud};
	# deal with non integer aantal - swap aantal and inhoud
	if($aant != int($aant)) { 
	    ($aant, $inh) = ($inh, $aant) 
	};
	$aant = int($aant);
        if($aant > 1) {
            if($h{verpakkingce} != "") {
                $h{kassaomschrijving} .= " $inh $h{eenheid} ($aant X $h{verpakkingce})";
            } else {
                $h{kassaomschrijving} .= " $inh $h{eenheid} ($aant per order)";
            }
        } elsif($h{verpakkingce} != "") {
            $h{kassaomschrijving} .= " $inh $h{eenheid} ($h{verpakkingce})";
        } else {
            $h{kassaomschrijving} .= " $inh $h{eenheid})";
        }
	my $sth = prepare("SELECT put_odin(?, " .  # prcode
                                 "?, " .       # supplier  
                                 "?,  ?, " .   # descr      brand
                                 "?, " .       # size
                                 "?,  ?, " .   # wh_q       unit
                                 "?, " .       # whpri
                                 "?, " .       # btw 
                                 "?)",         # tstamp
		       $dbh);
        eval {
            $sth->execute( $h{bestelnummer},  
                           $h{leverancier},  
                           $h{kassaomschrijving}, $h{merk},
                           $inh,
                           $aant,    	 $h{eenheid},
                           $h{wh_pri},
                           $h{btw},
                           $tstamp);
        };
        if($dbh->err) {
            my $m = $@;
            $dbh->rollback;
            $dbh->disconnect;
            die("odin file line $line: $m");
        }
    }

    my $sth = prepare(
	'UPDATE wholesaler SET wh_update = ? WHERE wh_id = ?', $dbh);
    eval {
	$sth->execute($tstamp, $config->{ODIN}->{odin_wh_id});
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->rollback;
	$dbh->disconnect;
	die($m);
    }

    $dbh->commit;
    my $suffix = $tstamp;
    $suffix =~ s/\s.*//;
    $suffix =~ s/[\/.-]//g;
    rename "$datadir/$datafile", "$datadir/odin_csv.$suffix.zip";
    return $line;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    
    my $src_fh = $cgi->upload("odin_data_file");
    my $tf = "$datadir/$datafile";
    my $tgt_fh;
    my $raw_fh;

    open($tgt_fh, ">$tf") or die "Can't open $tf: $!"; 
    while(my $l = <$src_fh>) {
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
		  buttons        => "adm_do_odin_upload/adm_odin_file_done.template",
	);
    my %hdr_h =(  Pagename       => 'Odin File Processing Complete',
		  Title          => 'Odin File Processing Complete',
		  Nextcgi        => 'adm_odin.cgi',
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

    #syslog(LOG_ERR, "welcome - >$mem_id<");

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
