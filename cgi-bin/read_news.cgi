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

sub max {
    my ($a, $b) = @_;
    return $a if $a >= $b;
    return $b;
}

# get choice to read - last 5 or  all, option to mark all as read
sub get_vars {
    my ($cgi, $dbh) = @_;
    my $vals = $cgi->Vars;

    # we'll want members current last read no, current max article ID

    my $sth = prepare("SELECT max(news_id) FROM member_news", $dbh);
    $sth->execute();
    my $aref = $sth->fetchrow_arrayref;
    $sth->finish;
    my $max_news = $aref->[0];

    if(defined($vals->{MarkRead})) {
	my $sth = prepare("UPDATE members SET mem_news = ? WHERE mem_id = ?", 
			  $dbh);
	eval {
	    $sth->execute($max_news, $mem_id);
	};
	if(! $@) {
	    $dbh->commit;
	} else {
	    $dbh->rollback;
	}
    }
    $sth = prepare("SELECT mem_news FROM members where mem_id =?", $dbh);
    $sth->execute($mem_id);
    $aref = $sth->fetchrow_arrayref;
    $sth->finish;
    my $mem_news = $aref->[0];

    # if not reading all, try to give 5 old messages
    my $limit = 5;
    if(defined($vals->{ShowAll})) {
	# read all - give all messages
	$limit = $max_news;
    } else {
	# read all new messages + some old if there are less than
	# 5 new ones
	if($max_news > $mem_news) {
	    $limit = max($limit, $max_news - $mem_news);
	}
    }
    return($limit, $mem_news, $max_news);
}

sub doit {
    my ($config, $cgi, $dbh) =@_;
    my $temp;
    my $h;

    my ($limit, $mem_news, $max_news) = get_vars($cgi, $dbh);
    $config->{title} = "News Messages";
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  message     => $temp,
	);

    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => "/cgi-bin/read_news.cgi",,
		  mem_name    => $config->{mem_name},
		  BUTTONS     => "",
	);
    
    $tpl->assign(\%hdr_h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    my $sth = prepare("SELECT * FROM news ORDER BY news_id DESC LIMIT ?", 
		      $dbh);
    $sth->execute($limit);
    while ($h = $sth->fetchrow_hashref) {
	$h->{RowClass} = ($h->{news_id} > $mem_news) ?
	    "myorder" : "editok";
	my $tpb = new CGI::FastTemplate($config->{templates});
	$tpb->strict();
	$tpb->define( temp => ($h->{posted} eq $h->{modified} and 
			       $h->{author} eq $h->{updater}) ?
		      "read_news/no-update-news.template" : 
		      "read_news/update-news.template");
	$tpb->assign($h);
	$tpb->parse("MAIN" => "temp");
	$tpb->print("MAIN");
    }

    my $tpr = new CGI::FastTemplate($config->{templates});
    $tpr->strict();
    $tpr->define( foot => "read_news/news-delete.template" );
    $tpr->assign( $h );
    $tpr->parse("MAIN" => "foot");
    $tpr->print("MAIN");
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
