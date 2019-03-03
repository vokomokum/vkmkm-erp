#! /usr/bin/perl -w 
# $Id: adm_view_memord.cgi,v 1.2 2010/04/13 06:19:46 jes Exp jes $

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

# globals to make everyone's life easier
my $conf = "../passwords/db.conf";
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

sub get_products {
    my ($config,$cgi, $dbh) = @_;

    # get a list of all the pr_ids for this order
    my @products;
    my $h;
    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);

    my $sth = prepare("SELECT d.qty as order, p.pr_id, p.pr_cat, p.pr_sc, " .
		      "p.pr_desc, CAST(d.qty*p.pr_mem_price AS INTEGER) " .
		      "AS price, p.pr_wh, p.wh_prcode, pr_mem_price as ". 
		      "meml_unit_price FROM default_order AS d, " .
		      "product AS p WHERE d.pr_id = p.pr_id ".
		      "AND d.mem_id = ?", $dbh);
    $sth->execute($mem_id);
    push @products, $h while($h = $sth->fetchrow_hashref);

    $sth->finish;
    $dbh->commit;
    #dump_stuff("products", "$mem_id", "", \@products);
    my @pr_hashes = sort pr_sort @products;
    return \@pr_hashes;
    
}

sub print_html {
    my ($pr_hashes, $config, $cgi, $dbh) = @_;
    my $total = 0;

    my $tpl = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();
    $tpl->define(header => "common/header.template",
		 banner => ( $config->{is_admin} )
		 ? "common/adm-banner.template"
		 : "common/mem-banner.template",
		 cats => "common/category-links.template",
		 
	);

    my %hdr_h = (
	Pagename    => "View/Clear Default Order",
	Title	    => "View/Clear Default Order",
	Nextcgi	    => "/cgi-bin/view_default.cgi",
	mem_name    => $config->{mem_name},
	LINKS	    => "",
	total	    => "",
	BUTTONS     => "",
	DROP        => "",
	STUFF       => "",
	);


    $tpl->assign(\%hdr_h);
    #$tpl->parse( SUBTITLE => "subtitle" );
    admin_banner($config->{status}, "BANNER", "banner", $tpl, $config);

    $tpl->parse( MAIN => "header" );
    $tpl->print( "MAIN" );

    my $h;
    if(scalar(@{$pr_hashes}) == 0) {
	    my $tpn = new CGI::FastTemplate($config->{templates});
	    $tpn->define(line =>"view_default/no_order.template");
	    $tpn->parse( MAIN => "line" );
	    $tpn->print( "MAIN" );
	    $dbh->disconnect;
	    exit(0);
    }

    my $tph = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();
    $tph->define( header => "view_default/view_default_titles.template", );
    $tph->assign({});
    $tph->parse( MAIN => "header" );
    $tph->print("MAIN");

    foreach $h (@{$pr_hashes}) {
	$total += $h->{price};
	$h->{cost} = sprintf "%0.2f", $h->{price}/100;
	$h->{meml_unit_price} = sprintf "%0.2f", $h->{meml_unit_price}/100;
	$h->{RowClass} = "myorder";

	my $tplr = new CGI::FastTemplate( $config->{templates} );
	my $url_temp = "common/zap_url.template";
	if ($h->{pr_wh} == $config->{ZAPATISTA}->{zap_wh_id}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{ZAPATISTA}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BG}->{bg_wh_id} and 
		$config->{BG}->{$h->{pr_id}}) {
	    $url_temp = "common/zap_url.template";
	    $h->{wh_url} = $config->{BG}->{$h->{pr_id}};
	} elsif($h->{pr_wh} == $config->{BUBBLE_CLUB}->{bc_wh_id} and 
		$config->{BUBBLE_CLUB}->{$h->{pr_id}}) {
	    $url_temp = "common/bclub_url.template";
	    $h->{wh_url} = $config->{BUBBLE_CLUB}->{$h->{pr_id}};
	} else {
	    $url_temp = "common/no_url.template";
	    $h->{URL} = "";
	}

	$tplr->define(row => "common/mem_order_row.template",
		     url => $url_temp);
	$tplr->assign($h);
	$tplr->parse("URL", "url");
	    
	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;

    }
    my $tpf = new CGI::FastTemplate( $config->{templates} );
    $tpf->define( footer => "view_default/footer.template" ); 
    $tpf->strict();
    $tpf->assign( { RowClass=> "myorder", 
		    total => sprintf("%0.2f", $total/100) } );
    $tpf->parse(MAIN => "footer");
    $tpf->print("MAIN");
    $dbh->disconnect;
    exit 0;
}

sub doit {
    my ($config, $cgi, $dbh) = @_;

    my $vars = $cgi->Vars;
    #dump_stuff("vars", "", "", $vars);
    if(defined($vars->{"Delete"})) {
	my $sth = prepare("DELETE FROM default_order WHERE mem_id = ?", $dbh);
	$sth->execute($mem_id);
	$sth->finish;
	$dbh->commit;
    }
    my $pr_hashes = get_products( $config, $cgi, $dbh);
    print_html($pr_hashes, $config, $cgi, $dbh);
}

sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);
    $config->{caller} = $program;
    $config->{program} = $program;
    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "$program");

    my ($cgi, $dbh) = open_cgi($config);
    my ($status, $ord_no) = ($config->{status}, $config->{ord_no});

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
