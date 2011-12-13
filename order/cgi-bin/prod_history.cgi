#! /usr/bin/perl -w
# $Rev$
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
use Switch 'Perl6';
use voko;
use view_member;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $current_no;
my $status;
my $err_msgs = "";
my $config;
my %categories;
my %cat_descs;
my %sc_descs;

# sort by cat, subcat, desc alpha
sub pr_sort{
    my $aid = 100000 * $a->{pr_cat} + $a->{pr_sc};
    my $bid = 100000 * $b->{pr_cat} + $b->{pr_sc};
    my $cmp = ($sc_descs{$aid}->{sort_ord} <=> $sc_descs{$bid}->{sort_ord});
    return $cmp if($cmp != 0);
    return ($a->{pr_desc} cmp $b->{pr_desc});
}

# return an array of all voko products 
sub get_products {
    my ($cgi, $dbh) = @_;
    my @pr_ar;
    my %pr_hr;

    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    my $sth = prepare("SELECT m.pr_id, p.pr_desc, p.pr_cat, p.pr_sc, " .
		      "p.pr_wh, p.wh_prcode, n.members, m.ordered, " .
		      "m.adjusted, m.received, m.dropped, " .
		      "p.pr_mem_price, m.cost FROM product AS p, " .
		      "  (SELECT count(*), sum(meml_qty) AS ordered, ".
		      "  sum(meml_adj) AS adjusted, " .
		      "  sum(meml_pickup) AS received, pr_id, ".
		      "  sum(meml_pickup*meml_unit_price) AS cost, " .
		      "  sum(meml_qty - meml_adj) AS dropped " .
		      "FROM mem_line group by pr_id) AS m, " .
		      "(SELECT count(distinct mem_id) AS members, pr_id " .
		      "FROM mem_line GROUP BY pr_id) AS n " . 
		      "WHERE p.pr_active AND p.pr_id = m.pr_id AND " .
		      "n.pr_id = p.pr_id", $dbh);

    $sth->execute;

    while ( my $h = $sth->fetchrow_hashref ) {
    	my $pr_no = $h->{pr_id};
    	$h->{RowClass} = "myorder";
    	$h->{cost} = sprintf "%0.2f", $h->{cost}/100.0;
	$h->{pr_mem_price} =sprintf( "%0.2f", $h->{pr_mem_price} );
    	$h->{pr_desc} = $cgi->escapeHTML( $h->{pr_desc} );
	push @pr_ar, $h;
    }

    $sth->finish;
    $dbh->commit;
    my @sorted = sort pr_sort @pr_ar;

    return \@sorted;

}

sub print_html {
    my ($sorted, $config, $cgi, $dbh) = @_;

    #dump_stuff("print_html", "pr", "", $pr);
    #dump_stuff("print_html", "sorted", "", $sorted);

    my $tpl = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();
    $tpl->define(header => "common/header.template",
		 banner => "common/adm-banner.template",
		 cats   => "common/category-links.template",
		 subtitle => $config->{subtitle},
		 buttons  => "prod_history/history_header.template",
    );

    my %hdr_h = (
	Pagename    => "Product Ordering Summary",
	Title	    => "Product Ordering Summary",
	Nextcgi	    => "/cgi-bin/prod_history.cgi",
	mem_name    => $config->{mem_name},
	LINKS	    => get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh),
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse( STUFF => "buttons" );
    $tpl->parse( BUTTONS => "cats" );
    # $tpl->parse( SUBTITLE => "subtitle" );
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse( MAIN => "header" );
    $tpl->print( "MAIN" );

    my $last_cat = -1;
    my $last_sc = -1;
    my $line = 0;


    foreach my $h ( @{$sorted} ) {
	if ( $last_cat != $h->{pr_cat} ) {
	    $last_cat = $h->{pr_cat};
	    $last_sc = 99999;
	    print_title(
		"prod_history/category_bar.template",
		$last_cat,
		$categories{$last_cat},
		$cat_descs{$last_cat},
		$config
                );
	}
	if ( $last_sc != $h->{pr_sc} ) {
	    $last_sc = $h->{pr_sc};
	    print_sub_cat("prod_history/sub_cat_bar.template", $last_cat,
			  $last_sc, \%sc_descs, $config);
	};

    	my $tplr = new CGI::FastTemplate( $config->{templates} );
	my $url_temp = "common/dnb_url.template";
	if ( $h->{pr_wh} == $config->{DNB}->{dnb_wh_id} ) {
            if ( $h->{wh_prcode} < 10000 ) {
                $h->{PID} = sprintf "%04.4d", $h->{wh_prcode};
            } else {
		$h->{PID} =  $h->{wh_prcode};
	    }
	} elsif($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BG}->{bg_wh_id} and 
		$config->{BG}->{$h->{pr_id}}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{BG}->{$h->{pr_id}};
	} else {
	    $url_temp = "common/no_url.template";
	    $h->{URL} = "";
	}

	$tplr->define(row => "prod_history/prod_row.template",
		     url => $url_temp);
	$tplr->assign($h);
	$tplr->parse("URL", "url");
	    
    	$tplr->parse( MAIN => "row" );
    	$tplr->print();
    	$tplr = undef;
	
    }

    my $tplf = new CGI::FastTemplate( $config->{templates} );
    $tplf->define( footer => "prod_history/footer.template" );
    $tplf->assign({});
    $tplf->parse(MAIN => "footer");
    $tplf->print();
    $tplf = undef;

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my ($sorted) = get_products($cgi, $dbh);
    print_html($sorted, $config, $cgi, $dbh);
}


sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    $config = read_conf($conf);
    $config->{caller} = $program;
    $config->{program} = $program;
    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "$program");

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	$mem_id = process_login(0, $config, $cgi, $dbh);
    } else {
	$mem_id = handle_cookie(0, $config, $cgi, $dbh);
    }

    $current_no = $ord_no;

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
