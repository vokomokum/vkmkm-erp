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
use Encode;
use Spreadsheet::ParseExcel;
use voko;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $datadir = "../bclub_data";
my $datafile = "newdata";
my $mem_id;
my $ord_no;
my $status;
my $err_msgs = "";
my $config;
my $order_name = "";

my $xls_date = "";

sub process {
    my ($config, $cgi, $dbh) = @_;
    my $count = 0;
    my $bclub = "$datadir/$datafile";
    die("Can't find a Bubble Club data file $datadir/$datafile")
	if(not -f "$datadir/$datafile");
    my $parser   = Spreadsheet::ParseExcel->new();
    my $workbook = $parser->parse($bclub) or 
	die "Can't make sense of $bclub as an Excel spreadsheet: $!";
    my $ws_count = 0;
    my %rows;
    my $id;
    for my $worksheet ( $workbook->worksheets() ) {
	last if($ws_count++ > 0);
	my ( $row_min, $row_max ) = $worksheet->row_range();
	my ( $col_min, $col_max ) = $worksheet->col_range();
	my $row;
	for($row = $row_min; $row <= $row_max; ++$row) {
	    my $cell = $worksheet->get_cell( $row, 0);
	    next unless $cell;
	    next if $cell->value() ne 'Date';
	    $cell = $worksheet->get_cell( $row, 1);
	    die "Missing Date in column 2 of row $row" unless $cell;
	    $xls_date = $cell->value();
	    $xls_date =~ s/[+-]\d\d$//;
	    $cell = $worksheet->get_cell($row, 5);
	    $id = ($cell && $cell->value()) ? $cell->value() : "";
	    ++$row;
	    last;
	}
	die "Did not find a row with 'Date' and a date and time"
	    if($xls_date eq "");
	die "Missing Title and database date from spreadsheet" 
	    if(not $id or 
	       $id !~ /Bubble Club - (\d{4,4}.\d\d.\d\d \d\d:\d\d:\d\d)/);
	$id = $1;
	$id =~ s!/!-!g;
	my $sth = prepare(
	    'SELECT wh_update FROM wholesaler WHERE wh_id = ?', $dbh);
	$sth->execute($config->{BUBBLE_CLUB}->{bc_wh_id});
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
	if(not $h) {
	    $dbh->disconnect;
	    die "Could not find last update date for product file";
	}

        if($h->{wh_update} =~
           m!(\d+)[/-](\d+)[/-](\d+)\s+(\d+):(\d+):(\d+).*!) {
            $h->{wh_update} = sprintf("%02d-%02d-%02d %02d:%02d:%02d",
				      $1, $2, $3, $4, $5, $6);
        }

	if($h->{wh_update} ne $id) {
	    die "Products have been updated since this spreadsheet was " .
		"downloaded. Download a new spreasheet and edit that one";
	}
	die "This file is not newer than the current product data, it will not be processed" if($xls_date le $h->{wh_update});

	# create a hash of remaining rows
	for( ; $row <= $row_max; ++$row) {
	    my $cell = $worksheet->get_cell($row, 0);
	    next if(not defined($cell));
	    my $uf = $cell->value();
	    next if($uf !~ /^\d+/ );
	    my %hash;
	    $hash{row} = $row + 1;
	    $hash{wh_pr_id} = $uf;
	    die "invalid product code on ++$row $hash{wh_pr_id}" 
		if($hash{wh_pr_id} < 0 or $hash{wh_pr_id} != int($hash{wh_pr_id}));
	    $cell = $worksheet->get_cell($row, 1);
	    $hash{wh_descr} = encode('utf8', $cell->value());
	    die "Description can not be empty on ++$row" if(not $hash{wh_descr});
	    $cell = $worksheet->get_cell($row, 2);
	    $hash{wh_wh_q} = $cell->value();
	    die "invalid wholesale quantity  $hash{wh_wh_q} on row ++$row" 
		if($hash{wh_wh_q} < 1 or  $hash{wh_wh_q} != int( $hash{wh_wh_q}));
	    $cell = $worksheet->get_cell($row, 3);
	    $hash{wh_whpri} = int(($cell->value() + .005) *100);
	    die "invalid wholesale price on row ++$row" if($hash{wh_whpri} <= 0);
	    $cell = $worksheet->get_cell($row, 4);
	    $hash{wh_btw} = $cell->value();
	    die "invalid btw rate on row ++$row" if($hash{wh_btw} < 0);
	    $cell = $worksheet->get_cell($row, 5);
	    $hash{wh_url} = ($cell && $cell->unformatted()) ? encode('utf8', $cell->value()) : "";

	    die "Product code $hash{wh_pr_id} appears twice, on row 1 + $hash{wh_pr_id}->{row} and ++$row"
		if(defined($rows{$hash{wh_prid}}));
	    $rows{$row} = \%hash;
	}
    }

    $dbh->commit;
    my $sth = prepare("SELECT MAX(wh_pr_id) AS prmax FROM bclub_data", $dbh);
    $sth->execute;
    my $h = $sth->fetchrow_hashref;
    my $next_pr_id = 1;
    $next_pr_id = 1 + $h->{prmax} if(defined($h));
    # check that there's no attempt to preset a product code
    $sth = prepare("SELECT wh_pr_id, wh_last_seen FROM bclub_data WHERE wh_pr_id = ?", 
		   $dbh);
    my $upd_sth = prepare("UPDATE bclub_data SET wh_whpri = ?, " .
			  "wh_btw = cast(? as numeric(5, 2)), " .
			  "wh_descr = ?, wh_url = ?, wh_wh_q = ?, wh_prcode = ?, ".
			  "wh_last_seen = ?, " .
			  "wh_prev_seen = ?  WHERE wh_pr_id = ?", $dbh);
    my $ins_sth = prepare("INSERT INTO bclub_data (wh_pr_id, wh_whpri, wh_btw, " .
			  "wh_descr, wh_url, wh_wh_q, wh_last_seen, wh_prev_seen, " .
			  "wh_prcode) VALUES (?, ?, cast(? as numeric(5,2)), ?, " .
			  "?, ?, cast(? as timestamp), cast(? as timestamp), ?)", 
		       $dbh);

    foreach my $k (keys %rows) {
	if($rows{$k}->{wh_pr_id} != 0) {
	    $sth->execute($rows{$k}->{wh_pr_id});
	    $h = $sth->fetchrow_hashref;
	    if(not defined($h) or not $h) {
		$dbh->rollback;
		$dbh->disconnect;
		die "Product code $rows{$k}->{wh_pr_id} on row $k is not a product - the update file will not be processed";
	    }
	    eval {
		$upd_sth->execute($rows{$k}->{wh_whpri}, $rows{$k}->{wh_btw}, 
				  $rows{$k}->{wh_descr}, $rows{$k}->{wh_url},
				  $rows{$k}->{wh_wh_q}, $rows{$k}->{wh_pr_id}, 
				  $xls_date, $h->{wh_last_seen},
				  $rows{$k}->{wh_pr_id});
	    };
	    if($dbh->err) {
		my $m = $@;
		$dbh->rollback;
		$dbh->commit;
		die "$m";
	    }
	} else {
	    eval {
		$ins_sth->execute($next_pr_id, $rows{$k}->{wh_whpri},
				  $rows{$k}->{wh_btw}, $rows{$k}->{wh_descr},
				  $rows{$k}->{wh_url}, $rows{$k}->{wh_wh_q}, 
				  $xls_date, , $xls_date, $next_pr_id);
	    };
	    if($dbh->err) {
                my $m = $@;
                $dbh->rollback;
                $dbh->commit;
                die "$m";
            }
	    ++$next_pr_id;
	}
	++$count;
    }
    $sth = prepare("UPDATE wholesaler SET wh_update = ? WHERE wh_id = ?", $dbh);
    eval {
	$sth->execute($xls_date, $config->{BUBBLE_CLUB}->{bc_wh_id});
    };
    if($dbh->err) {
	my $m = $@;
	$dbh->rollback;
	$dbh->commit;
	die "$m";
    }
    $dbh->commit;
    my $suffix = $xls_date;
    $suffix =~ s![/: ]!!g;
    rename "$datadir/$datafile", "$datadir/bclubassor$suffix.xls";
    return $count;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    
    my $src_fh = $cgi->upload("bclub_data_file");
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
		  buttons        => "adm_bc/adm_bc_file_done.template",
	);
    my %hdr_h =(  Pagename       => 'Bubble Club File Processing Complete',
		  Title          => 'Bubble Club File Processing Complete',
		  Nextcgi        => 'adm_bclub.cgi',
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
