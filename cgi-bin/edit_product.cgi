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


# variables expected:
# for product code NN:
# pr_cat_NN pr_sc_NN pr_wh_q_NN, pr_margin_NN, pr_mem_q_NN, pr_wh_price_nn
# pr_mem_price_NN, pr_desc_NN, pr_btw_NN, pr_active_NN

sub get_vars {
    my ($cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my %updates;

    # first get a full product list
    my $h;
    my $sth = prepare('SELECT * FROM edit_pr_view', $dbh);
    my %prods;
    $sth->execute;
    $prods{$h->{pr_id}} = $h while($h = $sth->fetchrow_hashref);
    $sth->finish;

    # look for posted variables with changed values
    my %to_update;
    my @fix_sc;
    foreach my $k (keys(%{$vals})) {
	next if($k !~ /^(.*)_(\d+)$/);
	my ($col, $pid) = ($1, $2);
	if($k =~ /price/ or $k =~ /btw/) {
	    my $v = $vals->{$k};
	    $v =~ s/,/./;
	    $vals->{$k} = int(100.0 * $v + 0.5);
	}
	if($k =~ /active/) {
	    $vals->{$k} = ($vals->{$k} =~ /^N/i) ? "0" : "1";
	}
	# skip if we can't find the product ???
	next if(not defined($prods{$pid}));
	# skip if the input is no change
	next if($vals->{$k} eq $prods{$pid}->{$col});

	# if the category has changed, the sub_cat becomes 99999
	# copy the product record to the to-be-updated hash if it's
	# not there already
	
	push @fix_sc, $pid if($col eq "pr_cat");
	$to_update{$pid} = $prods{$pid} if(not defined($to_update{$pid}));
	$to_update{$pid}->{$col} = $vals->{$k};
    }
    # default all the sub-cats 
    foreach my $p_id (@fix_sc) {
	$to_update{$p_id}->{pr_sc} = 99999;
    }

    # now go apply the updates. Simple error reporting, just the
    # product code and an update failed message

    #dump_stuff("to_update", "", "", \%to_update);
    $sth = prepare('UPDATE product SET pr_cat = ?, pr_sc = ?, ' .
		   'pr_wh_q = ?, pr_margin = ?, pr_mem_q = ?, ' .
		   'pr_wh_price = ?, pr_mem_price = ?, pr_desc = ?,' .
		   'pr_btw = ?, pr_active = ? WHERE pr_id = ?', $dbh);
    foreach my $k (keys(%to_update)) {
	my $p = $to_update{$k};
	eval {
	    $sth->execute($p->{pr_cat}, $p->{pr_sc}, $p->{pr_wh_q},
			  $p->{pr_margin}, $p->{pr_mem_q},
			  $p->{pr_wh_price}, 
			  $p->{pr_mem_price},
                          $p->{pr_desc}, $p->{pr_btw}, $p->{pr_active},
			  $p->{pr_id});
	};
	#dump_stuff("\$\@", "", "", \$@) if($@);
	if($@) {
	    $dbh->rollback;
	    $err_msgs .= "<p>Product $p->{pr_id} update failed</p>";
	} else {
	    $dbh->commit;
	}
    }
    $sth->finish;
    $dbh->commit;
    # return a fresh sorted copy of products
    $sth = prepare('SELECT * FROM edit_pr_view', $dbh);
    my @prodlist;
    $sth->execute;
    push @prodlist, $h while($h = $sth->fetchrow_hashref);
    $sth->finish;
    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    my @sorted = sort pr_sort @prodlist;
    return \@sorted;
}

sub print_html {
    my ($pr, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  cats        => "common/category-links.template",
	);
    my %hdr_h =(  Pagename    => "Edit Products",
		  Title       => "Edit Products",
                  mem_name    => $config->{mem_name},
		  Nextcgi     => "edit_product.cgi",
		  LINKS       => get_cats(\%categories, \%cat_descs, 
					  \%sc_descs, $dbh),
		  STUFF       => '<p></p><input type="submit"'.
		  'name="Submit" value="Submit"/><p></p><p></p>',
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "cats");
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 
    my $last_cat = -1;
    my $last_sc = -1;
    my $line = 0;

    foreach my $h (@{$pr}) {
	#dump_stuff("edit_product", "", "", $h);
	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->define(row => "edit_product/edit_product_row.template");
	if($last_cat != $h->{pr_cat}) {
	    $last_cat = $h->{pr_cat};
	    print_title("edit_product/edit_pr_titles.template", $last_cat, 
			$categories{$last_cat}, $categories{$last_cat},
			$config);
	    $last_sc = 99999;
	}
	if($last_sc != $h->{pr_sc}) {
	    $last_sc = $h->{pr_sc};
	    print_sub_cat("edit_product/edit_subcat.template", $last_cat,
			  $last_sc, \%sc_descs, $config);
	};



	$h->{DROP} = make_dropdown($h->{pr_cat}, \%categories);
	$h->{SC_DROP} = make_scdrop($h->{pr_cat}, $h->{pr_sc}, \%sc_descs);
	$h->{pr_active} = ($h->{pr_active}) ? 'Y' : 'N';
	$h->{pr_desc} = escapeHTML($h->{pr_desc});
	$h->{pr_mem_price} = sprintf("%.2f", $h->{pr_mem_price}/100.0);
	$h->{pr_wh_price} = sprintf("%.2f", $h->{pr_wh_price}/100.0);
	$tplr->assign($h);
	$tplr->parse(MAIN => "row");

	$tplr->print();
	$tplr = undef;
    }
    print "</table>\n";
    my $tplf = new CGI::FastTemplate($config->{templates});
    $tplf->define(footer => "common/editcat_ftr.template");
    $tplf->assign({});
    $tplf->parse(MAIN => "footer");
    $tplf->print();
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $pr = get_vars($cgi, $dbh);
    print_html($pr, $config, $cgi, $dbh);
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
	$mem_id = process_login(1, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(1, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
