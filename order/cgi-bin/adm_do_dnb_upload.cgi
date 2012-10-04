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
my $datadir = "../dnbdata";
my $datafile = "newdata.zip";
my $mem_id;
my $ord_no;
my $status;
my $err_msgs = "";
my $config;
my $order_name = "";

#leverancier	ean	bestelnr	omschrijving	merk	kwaliteit	aantal	inhoud	eenheid	land	trefwoord	H	G	S	inkoopprijs	adviesprijs	btw	korting	statiegeld	gluten	suiker	lactose	zout	koemelk	soja	gist	plantaardig	memo	ingredienten	datum

#DNB		0189	light kaas 30+	Aurora	eko	4,50	1	kg	nld	kaas 30+	12	205	05	9,25	13,50	1	0,00	0,00	0	0	0	1	1	0	0	0	30+ jonge kaas		2009/01/30

# create a hash of column number to column name
sub make_col_hash {
    my ($fh, $dnb) = @_;
    my $line = <$fh>;

    die("file $dnb appears to be empty") if(not defined($line));
    
    die("$dnb does not look like a DNB product file - no bestelnr column") 
	if($line !~ /\tbestelnr\t/);
    my %col_names;
    # trim any cruft off the end
    $line =~ s/\s+$//;
    my $i = 0;
    my @names = split(/\t/, $line);
    die("$dnb does not look like a DNB product file - not enough columns")
	if(scalar(@names) < 30);
    map { $col_names{$i++} = $_ } @names;
    return \%col_names;
}

# get the key which identifies the file, to prevent running the same file
# twice. It will also check that the file being run is newer than the 
# old file
sub get_file_key {
    my ($fh, $dnb, $config, $dbh) = @_;
    my $line = <$fh>;

    if(not defined($line)) {
	$dbh->disconnect;
	die("file $dnb appears to be empty");
    }

    $line =~ s/\s+$//;
    if($line !~ m@DNB\t\t(\d+)\t\t(\d+)/(\d+)/(\d+)\s+(\d+):(\d+):(\d+)@) {
	$dbh->disconnect;
	die("$dnb does not look like a DNB product file - missing file's datestamp");
    }
    my($nr, $yr, $mo, $day, $hr, $min, $sec) = ($1, $2, $3, $4, $5, $6, $7);
    my $newkey ="$yr/$mo/$day $hr:$min:$sec";
    my $sth = prepare(
	'SELECT wh_update FROM wholesaler WHERE wh_id = ?', $dbh);
    $sth->execute($config->{DNB}->{dnb_wh_id});
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

    my $dnb = "$datadir/$datafile";
    die("Can't find a DNB data file $datadir/$datafile")
	if(not -f "$datadir/$datafile");

    my $iconv = $config->{iconv};
    die("Can't find $iconv which is required to convert the text into UTF-8")
	if(not -x $iconv);

    my $infile = "$config->{unzip} -c $dnb";
    my $iconv_cmd = "$infile | $iconv --from-code=ISO-8859-1 --to-code=UTF-8 -";
    open(DBD, "$iconv_cmd |") or die "Can't run $iconv_cmd: $!";
    my $fh = *DBD{IO};
    my $junk = <$fh>;
    $junk =  <$fh>;
    my $cols = make_col_hash($fh, $dnb);
    my $newkey = get_file_key($fh, $dnb, $config, $dbh);
    my $line = 1;
    my @btws = (0, 6, 21);
    
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

	next if($items < 30);
	for(my $i = 0; $i < scalar(@data); ++$i) {
	    $h{$cols->{$i}} = $data[$i];
	}
	$h{bestelnr} =~ s/^\s0*//;
	$h{bestelnr} = int($h{bestelnr});
	$h{omschrijving} .= " [$h{merk}]" if($h{merk} ne '');
	$h{aantal} =~ s/,/./;
	$h{inhoud} =~ s/,/./;
	$h{inkoopprijs} =~ s/,/./;
	$h{statiegeld} =~ s/,/./;
	$h{korting} =~ s/,/./;
	my $aant = $h{aantal};
	$h{wh_pri} = int(100 * $aant * $h{inkoopprijs});
	$h{statiegeld} = int(100 * $h{statiegeld});
	my $inh = $h{inhoud};
	# deal with non integer aantal - swap aantal and inhoud
	if($aant != int($aant)) { 
	    ($aant, $inh) = ($inh, $aant) 
	};
	$aant = int($aant);
	$h{omschrijving} .= " $inh $h{eenheid} ($aant per omdoos)";
	$h{btw} = $btws[$h{btw}];
	$sth = prepare("SELECT put_dnb(?, " .  # prcode
                                 "?,  ?, " .   # supplier   barcode
                                 "?,  ?, " .   # descr      brand
                                 "?,  ?, " .   # kwaliteit  size
                                 "?,  ?, " .   # wh_q       unit
                                 "?,  ?, " .   # land       trefw
                                 "?,  ?, " .   # col_h      col_g
                                 "?,  ?, " .   # vol_s      whpri
                                 "?,  ?, " .   # btw        korting
                                 "?,  ?, " .   # statieg    gluten
                                 "?,  ?, " .   # suiker     lactose
                                 "?,  ?, " .   # milk       salt
                                 "?,  ?, " .   # soya       yeast
                                 "?,  ?)",     # veg        tstmp
		       $dbh);
	    eval {
		$sth->execute( $h{bestelnr},  
			       $h{leverancier},  $h{ean},
			       $h{omschrijving}, $h{merk},
			       $h{kwaliteit},    $inh,
			       $aant,    	 $h{eenheid},
			       $h{land},         $h{trefwoord},
			       $h{H},		 $h{G},
			       $h{S},		 $h{wh_pri},
			       $h{btw},          $h{korting},
			       $h{statiegeld},   $h{gluten},
			       $h{suiker},       $h{lactose},
			       $h{zout},         $h{koemelk},
			       $h{soja},	 $h{gist},
			       $h{plantaardig},   $now);
	    };
	    if($dbh->err) {
		my $m = $@;
		$dbh->rollback;
		$dbh->disconnect;
		die($m);
	    }
    }

    $sth = prepare(
	'UPDATE wholesaler SET wh_update = ? WHERE wh_id = ?', $dbh);
    eval {
	$sth->execute($newkey, $config->{DNB}->{dnb_wh_id});
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->rollback;
	$dbh->disconnect;
	die($m);
    }

    $dbh->commit;
    $suffix =~ s/\///g;
    rename "$datadir/$datafile", "$datadir/dnbassor.$suffix.zip";
    return $line;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    
    my $src_fh = $cgi->upload("dnb_data_file");
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
		  buttons        => "adm_do_dnb_upload/adm_dnb_file_done.template",
	);
    my %hdr_h =(  Pagename       => 'DNB File Processing Complete',
		  Title          => 'DNB File Processing Complete',
		  Nextcgi        => 'adm_dnb.cgi',
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
