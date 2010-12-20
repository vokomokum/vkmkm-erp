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

my $MAXITEMS = 20;

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

# insert a new record if one given (there's a non-empty 'newbody' input
# field 
# if any other old news items are in the posted variables and they are
# different from the existing news entries, update the news fields
# returns a flag, true if there was a new news-posting and a count
# of the number of old postings to display
# all the updates will be done when this returns
sub get_vars {
    my ($cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my $sth;

    # if the user has filled in a new item (non blank body), insert it now
    my $new_news = 0;
    if(defined($vals->{newbody}) and $vals->{newbody} !~ /^\s*$/s ) {
	$sth = prepare("SELECT post_news(?, ?)", $dbh);
	$sth->execute($mem_id, $vals->{newbody}) ;
	$sth->finish;
	$dbh->commit;
	$new_news = 1;
    }
    my $items = ($new_news) ? $MAXITEMS : $MAXITEMS - 1;
    # we'll offer MAXITEMS news items 
    $sth = prepare("SELECT * FROM member_news LIMIT $items", $dbh);
    my @news;
    my $h;
    $sth->execute;
    push @news, $h while($h = $sth->fetchrow_hashref);
    $sth->finish;

    $sth = prepare("SELECT update_news(?, ?, ?)", $dbh);
    foreach my $h (@news) {
	my $nid = $h->{news_id};

	if(defined($vals->{"text_$nid"}) and 
	   $h->{news_text} ne $vals->{"text_$nid"}) {
	    $sth->execute($h->{news_id}, $mem_id, $vals->{"text_$nid"});
	    $dbh->commit;
	}
    }
    $sth->finish;
    return $new_news, $items;
}

sub doit {
    my ($config, $cgi, $dbh) =@_;
    my $temp;
    my $h;

    my ($new_news, $items) = get_vars($cgi, $dbh);
    $config->{title} = "Create/Edit News Postings";
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => ($config->{is_admin}) ?
		  "common/adm-banner.template" : "common/mem-banner.template",
		  message     => $temp,
	);

    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => "/cgi-bin/post_news.cgi",,
		  mem_name    => $config->{mem_name},
		  BUTTONS     => '<p></p><input type="submit" name="Submit" value="Submit"><p></p><p></p>',
	);
    
    $tpl->assign(\%hdr_h);
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    # if this is the first time through OR if the last time through, no new
    # posting was created, offer the user a blank form
    if(not $new_news) {
	my $tpb = new CGI::FastTemplate($config->{templates});
	$tpb->strict();
	$tpb->define( temp => "post_news/new-news.template");
	$tpb->assign({RowClass => "myorder"});
	$tpb->parse("MAIN" => "temp");
	$tpb->print("MAIN");
    }
       
    # now get the existing updates
    my $sth = prepare("SELECT * FROM news ORDER BY news_id DESC LIMIT ?", 
		      $dbh);
    $sth->execute($items);
    while ($h = $sth->fetchrow_hashref) {
	$h->{RowClass} = "myorder";
	my $tpb = new CGI::FastTemplate($config->{templates});
	$tpb->strict();
	$tpb->define( temp => ($h->{posted} eq $h->{modified} and 
			       $h->{author} eq $h->{updater}) ?
		      "post_news/no-update-post.template" :
		      "post_news/update-post.template");
	$tpb->assign($h);
	$tpb->parse("MAIN" => "temp");
	$tpb->print("MAIN");
    }

    my $tpr = new CGI::FastTemplate($config->{templates});
    $tpr->strict();
    $tpr->define( foot => "common/editcat_ftr.template" );
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
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    my ($cgi, $dbh) = open_cgi($config);

    if($program =~ /login/) {
	$mem_id = process_login(1, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(1, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);
    $dbh->disconnect;
    exit 0;

}
main;
