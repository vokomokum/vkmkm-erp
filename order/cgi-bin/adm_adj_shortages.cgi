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
use List::Util qw(min max);

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $status;
my $err_msgs = "";

sub get_shorts {
    my ($dbh) = @_;
    my %shorts;
    my $mem_names = mem_names_hash($dbh);

    my $sh_st = 
      'SELECT *  FROM sh_view WHERE ord_no = ?'; 
    my $sh_sth = prepare($sh_st, $dbh);
    $sh_sth->execute($ord_no);
    while(my $h = $sh_sth->fetchrow_hashref) {
	my $pr_id = $h->{pr_id};
	$h->{cost}  = sprintf "%0.2f", $h->{cost};
	$h->{unit_pr}  = sprintf "%0.2f", $h->{unit_pr};
	$h->{descr} = escapeHTML($h->{descr});
	$h->{mem_name} = $mem_names->{$h->{mem_id}};
	$h->{can_reduce} = min($h->{reduce_by}, ($h->{ordered} % $h->{wh_q}));
	next if(($status < 5) and (($h->{ordered} % $h->{wh_q}) == 0));
	next if(($status >= 5) and ($h->{wh_ord} == $h->{wh_rcv}));
	if(!defined($shorts{$pr_id})) {
	    $shorts{$pr_id} = {$h->{mem_id} => $h};
	} else {
	    $shorts{$pr_id}->{$h->{mem_id}} = $h;
	}
    }
    $sh_sth->finish;
    return (\%shorts);
}

# return an hash of submitted values, 
# key = product -> hash member->adjusted qty, 
sub get_vars {
    my ($config, $cgi) = @_;
    my %pr_dat;
    my $vals = $cgi->Vars;
    my %new_vals;

    $config->{show_members} = (defined($vals->{save_show})) ?
	$vals->{save_show} : 0;
    return \%new_vals  if(not defined($vals));

    $config->{show_members} = not $config->{show_members}  
    if(defined($vals->{Show}) or defined($vals->{Hide}));
    if($status == 3 or $status == 6) {
	foreach my $p (keys %{$vals}) {
	    my $q = $vals->{$p};
	    $q = 0 if($vals->{$p} eq '');
	    next if($p !~ /^p_(\d+)m_(\d+)$/);
	    if(!defined($new_vals{$1})) {
		$new_vals{$1} = {$2 => $q};
	    } else {
		$new_vals{$1}->{$2} = $q;
	    }
	}
    }

    return \%new_vals;
}

# sort by cat, subcat, desc alpha
sub pr_sort{
    return ($a->{pr_id} <=> $b->{pr_id}) if($a->{pr_id} != $b->{pr_id});
    return ($b->{qty} <=> $a->{qty});
}
					      

# we've got the submitted variables. Get the current database state
# and apply any changed values
sub do_changes {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my $new_vals = get_vars($config, $cgi);
    my $shorts = get_shorts($dbh);

    #dump_stuff("new_vals", "", "", $new_vals);
    #dump_stuff("shorts", "pre auto", "", $shorts);
    if(($status == 3) and defined($vals->{Auto})) {
	# go through the shortages, looking for products where the sum of
	# can_reduce == reduce_by. In those cases, insert new_vals 
	# records with the reduction applied
	for my $pid (keys %{$shorts}) {
	    my $sum_can_reduce = 0;
	    my $reduce_by = 0;
	    my $hash = $shorts->{$pid};
	    for my $mid (keys %{$hash}) {
		$sum_can_reduce += $hash->{$mid}->{can_reduce};
		$reduce_by = $hash->{$mid}->{reduce_by};
	    }
	    if($sum_can_reduce == $reduce_by) {
		# there is only one solution possible, fill it in
		for my $mid (keys %{$shorts->{$pid}}) {
		    $new_vals->{$pid}->{$mid} = 
			$shorts->{$pid}->{$mid}->{ordered} -
			$shorts->{$pid}->{$mid}->{can_reduce};
		}
	    }
	}
	#dump_stuff("shorts", "post auto", "", $shorts);

    }

    #dump_stuff("do_changes", "new_vals", "", $new_vals);
    #dump_stuff("do_changes", "shorts", "", $shorts);
    foreach my $pr_id (keys %{$new_vals}) {
	my $lines = $new_vals->{$pr_id};
	foreach my $mem (keys %{$lines}) {
	    if(defined($shorts->{$pr_id}) and 
		       defined($shorts->{$pr_id}->{$mem})) {
		my $h = $shorts->{$pr_id}->{$mem};
		if($h->{qty} != $lines->{$mem}) {
		    my $sth = prepare('SELECT add_order_to_member(?, ?, ?, ?)', $dbh);
		    eval {
			$sth->execute($pr_id, $lines->{$mem}, $mem, 
				      (($status == 3) ? 1 : 2) );
			$sth->fetchrow_arrayref;
		    };
		    if($@) {
			my $e = $@;
			$e =~ s/.*ERROR: *//;
			$e =~ s/\s*$//;
			if(length($err_msgs) == 0) {
			    my $tpl = new CGI::FastTemplate($config->{templates});
			    $tpl->strict();
			    $tpl->define( emsg      => "common/err_pr_title.template");
			    my %em = (err_msg => $e);
			    $tpl->assign(\%em);
			    $tpl->parse(MAIN => "emsg");
			    my $e = $tpl->fetch("MAIN");
			    $err_msgs =  $$e;
			    $tpl = undef;
			}
			$dbh->rollback();
			$h->{qty} = $lines->{$mem};
			my $tplr = new CGI::FastTemplate($config->{templates});
			$tplr->define(row => "adm_adj_shortages/adm_error_row.template");
			$tplr->assign($h);
			$tplr->parse(MAIN => "row");
			my $ee = $tplr->fetch("MAIN");
			$err_msgs = $err_msgs . $$ee;
			$tplr = undef;
		    } else {
			$dbh->commit;
		    }
		}
	    }
	}
    }

    $config->{buttons}  = "adm_adj_shortages/adm_adj_save.template";
    $config->{divider} = ($config->{show_members}) ?
	"adm_adj_shortages/adm_titles_mem.template" :
	"adm_adj_shortages/adm_titles.template";
    if($status == 3) {
	$config->{divider} = ($config->{show_members}) ?
	    "adm_adj_shortages/adm_titles_mem_auto.template" :
	    "adm_adj_shortages/adm_titles_auto.template";
	$config->{title}    = "Adjust Order Shortages";
	$config->{buttons}  = "adm_adj_shortages/adm_adj_auto_save.template";
	$config->{row}      = ($config->{show_members}) ? 
	    "adm_adj_shortages/adm_editrow_mems_auto.template" : 
	    "adm_adj_shortages/adm_editrow_auto.template";
    } elsif($status == 6) {
	$config->{title}   = "Adjust Delivery Shortages";
	$config->{row}     = ($config->{show_members}) ? 
	    "adm_adj_shortages/adm_editrow_mems.template" : 
	    "adm_adj_shortages/adm_editrow.template";
    } else {
	$config->{title}   = "View Order Shortages";
	$config->{row}     = ($config->{show_members}) ? 
	    "adm_adj_shortages/adm_nothisorder_mems.template" : 
	    "adm_adj_shortages/adm_nothisorder.template";
	$config->{buttons} = "adm_adj_shortages/adm_nobuttons.template";
        $config->{divider}  = ($config->{show_members}) ? 
	    "adm_adj_shortages/adm_titles_nothisorder_mems.template":
	    "adm_adj_shortages/adm_titles_nothisorder.template";
    }
    $config->{nextcgi}  = "/cgi-bin/adm_adj_shortages.cgi";

}

sub print_html {
    my ($prh, $config, $cgi, $dbh) = @_;
    my @pra;
    my $last_pid = 0;
    my $color_flip = 1;

    for my $pid (keys %{$prh}) {
	my $hash = $prh->{$pid};
	for my $line (values %{$hash}) {
	    push @pra, $line;
	}
    }

    my @pr = sort pr_sort @pra;
    
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
		  banner      => "common/adm-banner.template",
		  prbuttons   => $config->{buttons});
    my %hdr_h =(  Pagename    => $config->{title},
		  Title       => $config->{title},
		  Nextcgi     => $config->{nextcgi},
		  mem_name    => $config->{mem_name},
		  showhide    => $config->{show_members} ?
		  "Hide" : "Show",
	);


    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "prbuttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    $tpl->clear(1);

    print "$err_msgs<p/>" if(length($err_msgs) > 0); 
    my $total = 0;
    my $line = 0;

    foreach my $h (@pr) {
	if(($line %20) == 0) {
	    print_title($config->{divider}, $line, "Description", $config);
	}
	++$line;
	if($h->{pr_id} != $last_pid) {
	    $last_pid = $h->{pr_id};
	    $color_flip ^= 1;
	}
	
	$h->{RowClass} = ($color_flip) ? "editok" : "myorder";
	$h->{Qty} = ($h->{reduce_by} == 0) ? "qtyinpgry" : "qtyinp";
	my $tplr = new CGI::FastTemplate($config->{templates});
	$tplr->define(row => $config->{row});
	$tplr->assign($h);
	$tplr->parse(MAIN => "row");
	$tplr->print();
	$tplr = undef;
    }
    my $tplf = new CGI::FastTemplate($config->{templates});
    printf '</table><input type="hidden" name="save_show" value="%d"</form></body></html>', $config->{show_members};
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    do_changes($config, $cgi, $dbh);
    my $pr = get_shorts($dbh);
    print_html($pr, $config, $cgi, $dbh);
}
    

	     
sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);
    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;

    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "Running as $program");

    my ($cgi, $dbh) = open_cgi($config);
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});


    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
