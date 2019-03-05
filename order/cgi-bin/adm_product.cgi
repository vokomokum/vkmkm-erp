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
my $status;
my $ord_no;
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
    my ($cgi, $dbh) = @_;
    my @pr_ar;
    my %pr_hr;

    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    my $sth = prepare('SELECT * FROM product WHERE pr_active', $dbh);
    $sth->execute;
    while(my $h = $sth->fetchrow_hashref) {
	my $pr_no = $h->{pr_id};
	$h->{pr_desc} = $cgi->escapeHTML($h->{pr_desc});
	$pr_hr{$pr_no} = $h;
	push @pr_ar, $h;
    }
    $sth->finish;
    my @sorted = sort pr_sort @pr_ar;
    return \@sorted, \%pr_hr;
}

sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my %new_vals;
    my %pids;;

    my ($sorted, $pr_hr) = get_products($cgi, $dbh);
    return (\%pids, $sorted, $pr_hr) if(not defined($vals));

    # inputs are checkbox product IDs
    foreach my $box (keys %{$vals}) {
	my $pid = $vals->{$box};
	$pid =~ s/x_(\d+)/$1/;
	$pids{$pid} = 1 if(defined($pr_hr->{$pid}));
    }
    return (\%pids, $sorted, $pr_hr, $vals);
}

sub do_changes {
    my ($config, $cgi, $dbh) = @_;
    my ($pids, $sorted, $pr_hr, $vals) = get_vars($config, $cgi, $dbh);
    do_edit($pids, $sorted, $pr_hr, $config, $cgi, $dbh) if(scalar(keys %{$pids}));
    
    my $tpl = new CGI::FastTemplate($config->{templates});
    $config->{title}    = (defined($vals->{ALL})) ? "Edit All Products" :
			   "Edit Current Products";

    $config->{buttons}  = "common/edit_product_buttons.template";
    $config->{nextcgi}  = "adm_product.cgi";
    $config->{row}      = "adm_product/pick-product-row.template";
    $config->{footers}  = "common/nototal_footer.template";

    $tpl->strict();
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
                  mbanner        => "common/mem-banner.template",
		  cats           => "common/category-links.template",
		  buttons        => $config->{buttons});
    my %hdr_h =(  Pagename => $config->{title},
		  Title    => $config->{title},
		  Nextcgi  => $config->{nextcgi},
		  LINKS    => get_cats(\%categories, \%cat_descs, 
				       \%sc_descs, $dbh),
		  ALL      => (defined($vals->{ALL})) ?
		  "CHECKED" : "",
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(STUFF => "buttons");
    $tpl->parse(BUTTONS => "cats");
    if(! $config->{is_admin}) {
	admini_banner($status, "BANNER", "mbanner", $tpl, $config);
    } else {
	admin_banner($status, "BANNER", "banner", $tpl, $config);
    }
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 
    my $total = 0;
    my $last_cat = -1;
    my $last_sc = -1;
    my $line = 0;

    foreach my $h (@{$sorted}) {
	if($last_cat != $h->{pr_cat}) {
	    $last_cat = $h->{pr_cat};
	    $last_sc = -1;
	    print_title("adm_product/edit-titles.template", $last_cat, 
			$categories{$last_cat}, $config);
	}
	if ( $last_sc != $h->{pr_sc} ) {
	    $last_sc = $h->{pr_sc};
	    print_sub_cat("adm_product/edit-sub_cat.template", $last_cat,
			  $last_sc, \%sc_descs, $config);
	    };

	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->define(row => $config->{row});
	$h->{checked} = (defined($pids->{$h->{pr_id}})) ? "CHECKED" : "";
	$h->{RowClass} = ($h->{pr_active}) ? "myorder" : "editok";
	$h->{mem_price} = sprintf "%0.2f", $h->{pr_mem_price} / 100.0;
	$h->{wh_price} = sprintf "%0.2f", $h->{pr_wh_price} / 100.0;
	$h->{active} = ($h->{pr_active}) ? "Yes" : "No";
        $h->{URL} = "";
        $tplr->define(row => $config->{row});
        $tplr->assign($h);

	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;
    }

    my $tplf = new CGI::FastTemplate($config->{templates});
    $tplf->define(footer => $config->{footer});
    $tplf->parse(MAIN => "footer");
    $tplf->print();
    $tplf = undef;
}

sub do_edit {
    my ($pids, $sorted, $pr_hr, $config, $cgi, $dbh) = @_;
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    do_changes($config, $cgi, $dbh);
}
    
sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);

    openlog( $program, LOG_PID, LOG_USER );

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	process_login(1, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
