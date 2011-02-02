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


sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my %parse_hash;
    my %sql;
    my %vals_2_db = (Member => "mem_id",
		     Email  => "mem_email",
		     Forename => "mem_fname",
		     Lastname => "mem_lname");

    $config->{nextcgi} = "adm_memedit.cgi";
    return if(not defined($vals));

    if(defined($vals->{"Create"})) {
	$config->{Member} = 0;
	$cgi->{nextcgi} = "mem_edit.cgi";
	return;
    }

    my $selectors = 0;
    foreach my $k (qw(Member Email Forename Lastname)) {
	$parse_hash{$k} = "";
	next if(!defined($vals->{$k}));
	my $v =~ s/\s*$//;
	$v =~ s/^\s*//;
	next if($v eq "");
	$parse_hash{$k} = escapeHTML($v);
	$sql{$vals_2_db{$k}} = $v;
	$selectors += 1;
    }
    # if this is the first time, no Edit button
    # will appear in $vals
    return \%parse_hash if(not defined($vals->{Edit}));

}


sub print_html_no_select {
    my ($parse_hash, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "header.template",
                  banner      => "adm-banner.template",
		  prbuttons   => "adm-memedit.template",
		  footer      => "nototal_footer.template");
    my %hdr_h =(  Pagename    => "Edit/Create Member",
		  Title       => "Edit/Create Member",
		  Nextcgi     => $config->{nextcgi},
		  mem_name    => $config->{mem_name},
	);


    $tpl->assign(\%hdr_h);
    $tpl->assign($parse_hash);
    $tpl->parse(FOOTER => "footer");
    $tpl->parse(BUTTONS => "prbuttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->assign(\%hdr_h);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    my $tplf = new CGI::FastTemplate($config->{templates});
    $tplf->define(footer => $config->{footer});
    $tplf->assign({});
    $tplf->parse(MAIN => "footer");
    $tplf->print();
}


	     
sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    $config = read_conf($conf);

    openlog( $program, LOG_PID, LOG_USER );

    my ($cgi, $dbh) = open_cgi($config);
    if($program =~ /mem-login/) {
	process_login(1, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }
    my $sth = prepare('SELECT ord_no, ord_status  FROM order_header', $dbh);
    $sth->execute;
    my $aref = $sth->fetchrow_arrayref;
    if(not defined($aref)) {
	die "Could not get order no and status";
    }
    $sth->finish;

    ($ord_no,  $status) = @{$aref};
    my ($junk, $buttons) = get_vars($cgi);
    if(! defined($buttons->{Member})) {
	get_mem_no();  # never returns
    } else {
	$mem_id = int($buttons->{Member});
    }

    $sth = prepare('SELECT memo_commit_closed IS NOT NULL ' .
		   'FROM mem_order WHERE mem_id = ? AND ord_no = ?', $dbh);
    $sth->execute($mem_id, $ord_no);
    $aref = $sth->fetchrow_arrayref;
    $config->{committed} = (defined($aref) and $aref->[0] ne '0') ? 1 : 0;
    $sth->finish;

    doit($cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
