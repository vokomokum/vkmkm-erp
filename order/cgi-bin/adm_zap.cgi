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
use Spreadsheet::WriteExcel;
use voko;

my $conf = "../passwords/db.conf";

# globals to make everyone's life easier
my $mem_id;
my $status;
my $ord_no;
my $err_msgs = "";
my %categories;
my %cat_descs;
my %sc_descs;

my $change = "#ff9090";
my $nochange = "#boffbo";

my $dir = "data";
mkdir $dir, 0755;
my $workbook;
my $worksheet;
my $fname = "zapatista/zapatista.xls";

# create a new spreadsheet whenever this runs
sub open_spreadsheet{
    my ($config, $cgi, $dbh) = @_;
    $workbook = Spreadsheet::WriteExcel->new("../$dir/$fname");
    $workbook->set_properties(utf8=>1);
    $worksheet = $workbook->add_worksheet();
    $worksheet->protect();

    my $fmt_date = $workbook->add_format(num_format=>'dd-mm-yyyy hh:mm:ss', 
					 align=>'center', locked=>0);
    my $fmt_int = $workbook->add_format(num_format=>0, align=>'center',
					locked=>0);
    my $fmt_dec = $workbook->add_format(num_format=>'#.#0', align=>'center',
					locked=>0);
    my $fmt_btw = $workbook->add_format(num_format=>'0.#', align=>'center',
					locked=>0);
    my $fmt_txt = $workbook->add_format(num_format => "@", align=>'left',
					locked=>0);
    my $fmt_lck = $workbook->add_format(num_format => "@", align=>'left', 
					locked=>1);
    my $fmt_lckmerge = $workbook->add_format(num_format => "@", align=>'left', 
					locked=>1);
    my $fmt_center = $workbook->add_format(num_format => "@", align=>'center',
					   locked=>0);
    # pr_code descr qty price btw url
    #  A      B      C    D    E   F   
    $worksheet->set_column('A:A', 7, $fmt_int);
    $worksheet->set_column('B:B', 50, $fmt_txt);
    $worksheet->set_column('C:C', 7, $fmt_int);
    $worksheet->set_column('D:D', 8, $fmt_dec);
    $worksheet->set_column('E:E', 6, $fmt_btw);
    $worksheet->set_column('F:F', 80, $fmt_txt);
    $worksheet->set_column('G:J', 8,  $fmt_txt);
    $worksheet->merge_range('A1:G6', 'Vertical and horizontal', $fmt_lckmerge);
    my $text = "";
    my $l;
    open(INST, "../templates/adm_zap/spreadsheet_inst.txt") or 
	die "Can't open templates/adm_zap/spreadsheet_inst.txt: $!";
    $text .= $l while($l = <INST>);
    close(INST);
    $worksheet->write('A1', $text, $fmt_lck);
    my $sth = prepare(
	'SELECT wh_update FROM wholesaler WHERE wh_id = ?', $dbh);
    $sth->execute($config->{ZAPATISTA}->{zap_wh_id});
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
    my $cutoff = $h->{wh_update};
    $cutoff =~ s/[+-]\d\d$//;
    $worksheet->write('A8', 'Date', $fmt_lck);
    $worksheet->write_date_time('B8', $cutoff, $fmt_date);
    $worksheet->write('F8', "Zapatista Coffee - $cutoff", $fmt_lck);
    $cutoff = $h->{wh_update};

    my @headings = ('Pr code', 'Description', 'Qty', 'Price', 'BTW%', 'URL'); 
    $worksheet->write_row('A9', \@headings, $fmt_lck);
    my $row = 10;

    $sth = prepare('SELECT * FROM zapatistadata WHERE wh_last_seen = ? ORDER BY wh_pr_id' , $dbh);
    $sth->execute($cutoff);
    while($h = $sth->fetchrow_hashref) {
	$worksheet->write($row, 0, $h->{wh_pr_id}, $fmt_int);
	$worksheet->write($row, 1, decode('utf8', $h->{wh_descr}), $fmt_txt);
	$worksheet->write($row, 2, $h->{wh_wh_q}, $fmt_int);
	$worksheet->write($row, 3, $h->{wh_whpri}/100., $fmt_dec);
	$worksheet->write($row, 4, $h->{wh_btw}, $fmt_btw);
	$worksheet->write($row, 5, decode('utf8',$h->{wh_url}), $fmt_txt);
	++$row;
    }
    $sth->finish;
    $workbook->close();
}
	

# display stats and select what we want to do
# actual updates come later

# get statistics over changes in need of processing
# returns a collection of array refs:
#   @voko_changed - active voko products which need updating
#   @voko_dropped - products which are no longer available
#   @voko_same    - active products which haven't changed and need no attention
#   @new_zap      - products which are new in this Zapatista list
#   @zap_maybe    - Zapatista products not currently on offer, but maybe later
#   @zap_all      - all Zapatista products which are not vokomokum products
# each array element is a row from Zapatista_products view

sub get_stats {
    my ($new_vals, $config, $cgi, $dbh) = @_;
    my $sth;
    my $h;
    my $a;
    my (@voko_changed, @voko_dropped, @voko_same, @new_zap, 
	@zap_maybe, @zap_all);

    if($config->{choice} == 0) {
	#$sth = prepare("UPDATE zapatistadata SET is_seen = 'f'", $dbh);
	#$sth->execute;
	#$sth->finish;
    }
    # make sure the is_product flag are correctly set
    $sth = prepare("UPDATE zapatistadata SET is_product = (wh_prcode IN " .
		   "(SELECT wh_prcode FROM product WHERE pr_wh = ?))", $dbh);
    $sth->execute($config->{ZAPATISTA}->{zap_wh_id});
    $sth->finish;
    $dbh->commit;

    # get timestamps from wholesaler record
    $sth = prepare("SELECT * FROM zap_interval()", $dbh);
    $sth->execute;
    $a = $sth->fetchrow_arrayref;
    my ($newest, $penult) = @{$a};
    if(not defined($newest)) {
	$newest = "2009-08-31 10:47:34+02";
	$newest =~ s/[+-]\d\d$//;
	$penult = "2009-08-31 10:47:34+02";;
	$penult =~ s/[+-]\d\d$//;
    }

    $config->{newest} = $newest;
    $config->{newest} =~ s/\+.*//;
    $config->{penult} = $penult;
    $config->{penult} =~ s/\+.*//;
    $sth->finish;

    # step through the products
    $sth = prepare("SELECT * from zap_products ORDER BY wh_pr_id", $dbh);
    $sth->execute;
    while($h = $sth->fetchrow_hashref) {
	$h->{reprice} = 0;
	my $wid = $h->{wh_pr_id};
	# merge input values into record
	if(defined($new_vals->{$wid})) {
	    my $nv = $new_vals->{$wid};
	    foreach my $k (keys %{$nv}) {
		$h->{$k} = $nv->{$k};
	    }
	}
	if(defined($h->{pr_id})) {
	    # it's in the voko product list
	    if(not $h->{pr_active}) {
		# no longer an active product, but was dropped 
		# a while ago, ignore
		next if($h->{wh_last_seen} lt $penult);
		# no longer an active product, just now dropped,
		# we want to display it as dropped (so you can run
		# this more than once and see the changes)
		if($h->{wh_last_seen} lt $newest) {
		    push @voko_dropped, $h;
		    next;
	 	}
		# in voko list, but not active, keep the maybe/never status
		push @zap_maybe, $h if(not $h->{is_skipped});
		push @zap_all, $h if($h->{is_skipped});
		next;
	    }
	    # it's in the voko product list, but no longer a Zapatista product
	    if($h->{wh_last_seen} lt $newest) {
		push @voko_dropped, $h;
		next;
	    }
	    # active products where there are changes or the
	    # current price exceeds the current margin (e.g
            # price with btw = 5.00, margin = 5% price should be 5.25
            # if margin were 6%, price would be  5.30
            # we report if item is 5.30 or more - change the price or the 
            # margin
	    if($h->{wh_wh_q}  != $h->{pr_wh_q} or
	       $h->{wh_whpri} != $h->{pr_wh_price} or
	       $h->{wh_btw}   != $h->{pr_btw} or
	       $h->{rec_pr}   >  $h->{pr_mem_price}) {
		push @voko_changed, $h;
		next;
	    }
	    # flag changes which are over-prices
	    if($h->{over_marg}  < $h->{pr_mem_price}) {
		$h->{reprice} = 1;
		push @voko_changed, $h;
		next;
	    }

	    # active product, no real changes
	    push @voko_same, $h;
	    next;
	}
	# Zapatista product not in the voko list. Skip if no longer a Zapatista product
	next if($h->{wh_last_seen} lt $newest);

	# display as new product unless already classified
	if($h->{wh_last_seen} eq $newest and $h->{wh_prev_seen} eq $newest
	    and not $h->{is_seen}) {
	    push @new_zap, $h;
	    next;
	}
	next if($h->{is_seen});
	push @zap_all, $h;
	push @zap_maybe, $h if(not $h->{is_skipped});
    }
    $sth->finish;
    return (\@voko_changed, \@voko_dropped, \@voko_same, 
	    \@new_zap, \@zap_maybe, \@zap_all);}


# see if we know what mode we're in
sub get_mode {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;

    return if(not defined($vals));
    
    if(defined($vals->{hidden_choice})) {
	$config->{choice} = $vals->{hidden_choice};
	return;
    }
    
    for(my $i = 1; $i < 6; ++$i) {
	if(defined($vals->{"t$i"})) {
	    $config->{choice} = $i;
	    return;
	}
    }
}

# mode not chosen, prompt for it
# choices are: voko-chnaged products  
#              new Zapatista products
#              all non-excluded Zapatista products
#              all Zapatista products

sub get_choice {
    my ($voko_changed, $voko_dropped, $voko_same, 
	    $new_zap, $zap_maybe, $zap_all, $config, $cgi, $dbh) = @_;
    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    my $buttons = {}; # 
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  buttons        => "adm_zap/zap-prod-type.template");
    my %hdr_h =(  Pagename       => $config->{title},
		  Title          => $config->{title},
		  Nextcgi        => $config->{nextcgi},
		  mem_name       => $config->{mem_name},
		  changed        => scalar(@{$voko_changed}),
		  dropped        => scalar(@{$voko_dropped}),
		  new            => scalar(@{$new_zap}),
		  maybe          => scalar(@{$zap_maybe}),
		  all            => scalar(@{$zap_all}),
		  filename       => "/$fname",
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print '</form></body></html>';
    exit 0;
}

# get all the form variables into a hash by wh_id
# variables will be d_wid = description, c_wid == category (int)
# q_wid = member quantity (int), p_wid = member price (float), 
# m_wid = margin (int), s_prid = letter (AMN)
# the has will be merged into the wholesale records hash
sub get_vars {
    my ($config, $cgi, $dbh) = @_;
    
    get_mode($config, $cgi, $dbh);
    my %inputs;
    my @updates;
    my @to_edit;
    my ($type, $wid);
    my $vals = $cgi->Vars;

    foreach my $k (keys (%{$vals})) {
	if($k =~ /^([dcqpmsi])_(\d+)$/) {
	    ($type, $wid) = ($1, $2);
	    my $v = $vals->{$k};
	    $v =~ s/,/./  if($type eq 'p');
	    $v = int(100 * $v) if($type eq 'p');
	    $v = uc($v) if($type eq 's');
	    $inputs{$wid} = {} if(not defined($inputs{$wid}));
	    $inputs{$wid}->{$type} = $v;
	    push @updates, $wid if($type eq 's' or $type eq 'i');
	    push @to_edit, $wid if($type eq 's' and $v eq 'A');
	}
    }

    if(scalar(@updates) == 0) {
	$config->{choice} ^= 8 if(defined($vals->{toggle_list}));
	return \%inputs;
    }
    if($config->{choice} == 1) {
	foreach $wid (@updates) {
	    next if(not defined($inputs{$wid}->{s}));
	    my $zapst = prepare("SELECT wh_wh_q, wh_btw, wh_whpri, ".
				"wh_prcode, wh_descr FROM zapatistadata ".
				"WHERE wh_pr_id = ?", $dbh);
	    $zapst->execute($wid);
	    my $h = $zapst->fetchrow_hashref;
	    $zapst->finish;
	    next if(not defined($h));
	    my $sth = prepare("UPDATE product SET pr_margin = ?, ".
			      "pr_mem_price = ?, pr_desc = ?, ".
			      "pr_wh_q = ?, pr_btw = ?, pr_wh_price = ?,".
			      "wh_desc = ? ".
			      "WHERE pr_id = (SELECT pr_id FROM ".
			      "product where wh_prcode = ?)", $dbh);
	    $sth->execute($inputs{$wid}->{m},
			  $inputs{$wid}->{p},
			  $inputs{$wid}->{d},
			  $h->{wh_wh_q}, $h->{wh_btw}, 
			  $h->{wh_whpri}, $h->{wh_descr},
			  $wid);
	    $sth->finish;
	    $dbh->commit;
	    delete $inputs{$wid};
	}

	return \%inputs;
    }
    # dual modes - 2, 3, 4 are product editing modes where 
    # 2, 3, 4 users are classifying lines ahd/or selecting lines
    #    for subsequent editing
    # modes 10, 11, 12 users are editing lines, but edits may be
    #    just classifications
    # first - deal with classifications
    
    return \%inputs if($config->{choice} < 2);

    # handle any reclassifications noe
    my $do_commit = 0;
    my $upd_sth = prepare("UPDATE zapatistadata SET is_seen = ?, ".
			  "is_skipped = ? WHERE wh_pr_id = ?", $dbh);

    foreach $wid (@updates) {
	# skip 'A' status, these are either records to be offered for
	# editing or inserts to be performed
	next if(not defined($inputs{$wid}));
	my $inp = $inputs{$wid};
	my $s = "";
	$s = $inp->{s} if(defined($inp->{s}));
	$s = $inp->{i} if(defined($inp->{i}));
	next if($s !~ /[XM]/i);
	$upd_sth->execute('t', (($s =~ /^[xX]/) ?
				't' : 'f'), $wid);

	$do_commit = 1;
	delete $inputs{$wid};
    }
    $upd_sth->finish;
    $dbh->commit if($do_commit);

    # now go through the records to be inserted (only applies if
    # form was submitted from an edit screen
    if($config->{choice} & 8) {
	$do_commit = 0;
	my $ins_sth = prepare("INSERT INTO product (pr_cat, pr_sc, ".
			      "pr_wh, pr_wh_q, pr_margin, pr_mem_q, ".
			      "pr_wh_price, pr_desc, wh_prcode, wh_desc, ".
			      "pr_btw, pr_mem_price) VALUES (?, ?, ".
			      "?, ?, ?, ?, ".
			      "?, ?, ?, ?, ".
			      "?, ?)", $dbh);


	my $zapst = prepare("SELECT wh_wh_q, wh_btw, wh_whpri, ".
			    "wh_prcode, wh_descr FROM zapatistadata ".
			    "WHERE wh_pr_id = ?", $dbh);

	foreach $wid (@updates) {
	    next if(not defined($inputs{$wid}) or 
		    not defined($inputs{$wid}->{i}));
	    my $inp = $inputs{$wid};
	    next if($inp->{i} !~ /A/i);
	    my $zapst = prepare("SELECT wh_wh_q, wh_btw, wh_whpri, ".
				"wh_prcode, wh_descr FROM zapatistadata ".
				"WHERE wh_pr_id = ?", $dbh);
	    $zapst->execute($wid);
	    my $h = $zapst->fetchrow_hashref;
	    $zapst->finish;

	    next if(not defined($h));
	    $do_commit = 1;
	    $ins_sth->execute($inp->{c}, 99999, 
			      $config->{ZAPATISTA}->{zap_wh_id}, $h->{wh_wh_q}, 
			      $inp->{m}, $inp->{q}, 
			      $h->{wh_whpri}, $inp->{d}, $wid, $h->{wh_descr},
			      $h->{wh_btw}, $inp->{p});
	    delete $inputs{$wid};
	}
	$ins_sth->finish;
	$dbh->commit if($do_commit);
    }
    # now set config->choice based on which type of submit was done
    $config->{choice} ^= 8 if(defined($vals->{toggle_list}));

    # ugly hackery
    foreach $wid (keys %inputs) {
	$inputs{$wid}->{i} = '' 
	    if(defined($inputs{$wid}->{s}) and $inputs{$wid}->{s} =~ /A/i);
    }
    return \%inputs;
	
}

# html_header common routine

sub html_header {
    my ($title, $buttons, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  buttons        => $buttons,
	);
    my %hdr_h =(  Pagename       => $title,
		  Title          => $title,
		  Nextcgi        => $config->{nextcgi},
		  newest         => $config->{newest},
		  penult         => $config->{penult},
		  mem_name       => $config->{mem_name},
		  mem_id         => $mem_id,
		  );

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
}

# deal with dropped products - mark inactive, remove from orders
# and report what's happened
sub do_dropped_products {
    my ($voko_dropped, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header  => "adm_zap/adm_zap_m1_dropped.template",
	);
    $tpl->assign({});
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    my $sth = prepare("UPDATE product SET pr_active = 'f' ".
		      "WHERE pr_id = ?", $dbh);
    my $exh = prepare("SELECT remove_product(?)", $dbh);

    my $updates = 0;
    foreach my $h (@{$voko_dropped}) {
	my $pid = $h->{pr_id};
	if($h->{pr_active}) {
	    $sth->execute($pid);
	    $exh->execute($pid);
	    $updates = 1;
	}
	my $tpr = new CGI::FastTemplate($config->{templates});
	$tpr->strict();
	$tpr->define( row => "adm_zap/adm_zap_m1_dropped_row.template");
	$tpr->assign($h);
	$tpr->parse(MAIN => "row");
	$tpr->print("MAIN");
    }
    $dbh->commit if($updates);
    $sth->finish;
    $exh->finish;
    print "</table>\n";
}

sub title_row {
    my ($config) = @_;

    my $tpr = new CGI::FastTemplate($config->{templates});
    $tpr->strict();
    $tpr->define( title => ($config->{choice} & 8) ?
		  "adm_zap/adm_zap_m101112_table.template" : 
		  "adm_zap/adm_zap_m234_table.template");
    $tpr->assign({});
    $tpr->parse(MAIN => "title");
    $tpr->print("MAIN");
}

# report products which have changed in terms of description, wh_q, rec. price, margin, 
sub do_changed_products {
    my ($voko_changed, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header  => "adm_zap/adm_zap_m1_changed.template",
	);
    $tpl->assign({});
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    my $sth = prepare("UPDATE product SET pr_wh_q = ?, pr_margin = ?, ".
		      "pr_mem_q = ?, pr_mem_price = ?, pr_desc = ?, ".
		      "pr_btw = ? WHERE pr_id = ?", $dbh);
    foreach my $h (@{$voko_changed}) {
	my $pid = $h->{pr_id};
	
	$h->{diff_desc} = ($h->{wh_descr} eq $h->{pr_desc}) ?
	    $nochange : $change;
	$h->{w_desc} = escapeHTML($h->{wh_descr});
	$h->{diff_w_qty} = ($h->{wh_wh_q} == $h->{pr_wh_q}) ?
	    $nochange : $change;
	$h->{diff_w_qty} = ($h->{wh_wh_q} == $h->{pr_wh_q}) ?
	    $nochange : $change;
	$h->{diff_wh_pr} = ($h->{wh_whpri} == $h->{pr_wh_price}) ?
	    $nochange : $change;
	$h->{whpri} = sprintf("%.2f", $h->{wh_whpri}/100.0);
	$h->{diff_pr} = ($h->{rec_pr} == $h->{pr_mem_price}) ?
	    $nochange : $change;
	$h->{min_pri} = sprintf("%.2f", $h->{rec_pr}/100.0);
	$h->{diff_btw} = ($h->{wh_btw} == $h->{pr_btw}) ?
	    $nochange : $change;

	$h->{p_desc} = escapeHTML($h->{pr_desc});
	$h->{pr_whpri} = sprintf "%.2f", $h->{pr_wh_price}/100.0;
	$h->{mprice} =  sprintf "%.2f", $h->{pr_mem_price}/100.0;
	$h->{PID} = ($h->{wh_pr_id} < 10000) ? 
	    sprintf "%04.4d", $h->{wh_pr_id} : $h->{wh_pr_id};
	my $tpr = new CGI::FastTemplate($config->{templates});
	$tpr->strict();
	$tpr->define( row => "adm_zap/adm_zap_m1_changed_row.template",
		      url => "common/zap_url.template");
	$tpr->assign($h);
	$tpr->parse("URL", "url");
	$tpr->parse(MAIN => "row");
	$tpr->print("MAIN");
    }
    print '</table><p/><input type="submit" name="Submit" value="Submit"/>'.
	'</form></body></html>';
    exit 0;
}


# mode 1 - display changes to existing products
# display will be in parts:
# 1) products no longer available and which are auto-deactivated when this runs


# 2) products where something has changed and which need updating. We don't f

# 3) products where the price is below the margin for whatever reason 
# (shouldn't happen) or price > what the margin requires (adjust price 
# up or margin down)
sub mode_1 {
    my ($voko_changed, $voko_dropped, $config, $cgi, $dbh) = @_;

    html_header("Product File Changes from Zapatista Coffee Product List",
		"adm_zap/adm_zap_mode_1.template", $config, $cgi, $dbh);

    do_dropped_products($voko_dropped, $config, $cgi, $dbh)
	if(scalar(@{$voko_dropped}));

    do_changed_products($voko_changed, $config, $cgi, $dbh)
	if(scalar(@{$voko_changed}));
}

# mode 2 - new Zapatista Coffee Products
# admin can make it a product while setting the description, category
# price, and margin, can mark it as a Maybe or a Never

sub mode_2 {
    my ($new_vals, $new_zap, $config, $cgi, $dbh) = @_;

    do_header_234("adm_zap/adm_zap_m2_title.template", $config, $cgi, $dbh);
    if($config->{choice} & 8) {
	modes_101112($new_vals, $new_zap, $config, $cgi, $dbh);
    }
    modes_234($new_vals, $new_zap, $config, $cgi, $dbh);
}

sub mode_3 {
    my ($new_vals, $zap_maybe, $config, $cgi, $dbh) = @_;

    do_header_234("adm_zap/adm_zap_m3_title.template", $config, $cgi, $dbh);
    if($config->{choice} & 8) {
	modes_101112($new_vals, $zap_maybe, $config, $cgi, $dbh);
    }
    modes_234($new_vals, $zap_maybe, $config, $cgi, $dbh);
}

sub mode_4 {
    my ($new_vals, $zap_all, $config, $cgi, $dbh) = @_;

    do_header_234("adm_zap/adm_zap_m4_title.template", $config, $cgi, $dbh);
    if($config->{choice} & 8) {
	modes_101112($new_vals, $zap_all, $config, $cgi, $dbh);
    }
    modes_234($new_vals, $zap_all, $config, $cgi, $dbh);
}

sub do_header_234 {
    my ($template,  $config, $cgi, $dbh) = @_;
    html_header("New Products in the  Zapatista Coffee Product List",
		"adm_zap/adm_zap_mode_1.template", $config, $cgi, $dbh);


    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header  => $template,
	);
    $tpl->assign({ mode => $config->{choice},
		   toggle => ($config->{choice} & 8) ?
		       "Return to Zapatista Coffee Product list" :  
		       "Edit New Products"});
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
}

sub do_footer_234 {
    my ($config) = @_;

    my $tpf = new CGI::FastTemplate($config->{templates});
    $tpf->strict();
    $tpf->define( footer => "adm_zap/adm_zap_m234_footer.template");
    $tpf->assign({ toggle => ($config->{choice} & 8) ?
		       "Return to Zapatista Coffee list" : "Edit New Products"});
    $tpf->parse(MAIN => "footer");
    $tpf->print("MAIN");
    exit 0;
}

# display rows for categorisation or selection for editing
sub modes_234 {
    my ($new_vals, $zap_hash, $config, $cgi, $dbh) = @_;
    my $sth = prepare("SELECT min_price(?, ?, ?, ?)", $dbh);
    my $line = 0;

    foreach my $h (@{$zap_hash}) {
	my $wid = $h->{wh_pr_id};
	my $nv = (defined($new_vals->{$wid}))?
	    $new_vals->{$wid} : {};
	$h->{p_desc} = escapeHTML($h->{wh_descr});
	$h->{pr_whpri} = sprintf "%.2f", $h->{pr_wh_price}/100.0;
	$h->{DROP} = make_dropdown(((defined($nv->{c})) ? 
			    $nv->{c} : 99999), \%categories);
	$h->{qqq} = (defined($nv->{q})) ? 
		   $nv->{q} : 1;
	$h->{mmm} = (defined($nv->{m})) ? 
	    $nv->{m} : 5;
	$sth->execute($h->{wh_whpri}, $h->{wh_btw}, 
		      5, $h->{wh_wh_q});
	my $mp = $sth->fetchrow_arrayref;
	$h->{rec_pr} = $mp->[0];
	$h->{mprice} =  sprintf "%.2f", $h->{rec_pr}/100.0;
	$h->{w_price} = sprintf "%.2f", $h->{wh_whpri}/100.0;
	$h->{sss} = (defined($nv->{s})) ? 
	    $nv->{s} : '';
	$h->{PID} = ($h->{wh_pr_id} < 10000) ? 
	    sprintf "%04.4d", $h->{wh_pr_id} : $h->{wh_pr_id};

	title_row($config) if($line == 0);
	$line = ++$line % 20;

	my $tpr = new CGI::FastTemplate($config->{templates});
	$tpr->strict();
	$tpr->define( row => "adm_zap/adm_zap_m2_row.template",
		      url => "common/zap_url.template");
	$tpr->assign($h);
	$tpr->parse("URL", "url");
	$tpr->parse(MAIN => "row");
	$tpr->print("MAIN");

    }
    do_footer_234($config);

}

# display edit rows for selected Zapatista Coffee products
sub modes_101112 {
    my ($new_vals, $zap_hash, $config, $cgi, $dbh) = @_;
    my $sth = prepare("SELECT min_price(?, ?, ?, ?)", $dbh);
    my $line = 0;

    foreach my $h (@{$zap_hash}) {
	my $wid = $h->{wh_pr_id};
	next if(not defined($new_vals->{$wid}));
	my $nv = $new_vals->{$wid};
	next if(not defined($nv->{i}));
	$h->{p_desc} = escapeHTML((defined($nv->{d})) ? 
				  $nv->{d} : $h->{wh_descr});
	$h->{pr_whpri} = sprintf "%.2f", $h->{pr_wh_price}/100.0;
	$h->{DROP} = make_dropdown(((defined($nv->{c})) ? 
			    $nv->{c} : 99999), \%categories);
	$h->{qqq} = (defined($nv->{q})) ? 
		   $nv->{q} : 1;
	$h->{mmm} = (defined($nv->{m})) ? 
	    $nv->{m} : 5;
	$sth->execute($h->{wh_whpri}, $h->{wh_btw}, 
		      $h->{mmm}, $h->{wh_wh_q});
	my $mp = $sth->fetchrow_arrayref;
	$h->{rec_pr} = $mp->[0];
	$h->{mprice} =  sprintf "%.2f", ((defined($nv->{p})) ?
				$nv->{p} : $h->{rec_pr})/100.0;
	$h->{w_price} = sprintf "%.2f", $h->{wh_whpri}/100.0;
	$h->{sss} = (defined($nv->{i})) ? 
	    $nv->{i} : '';
	title_row($config) if($line == 0);
	$line = ++$line % 20;
	$h->{PID} = ($h->{wh_pr_id} < 10000) ? 
	    sprintf "%04.4d", $h->{wh_pr_id} : $h->{wh_pr_id};

	my $tpr = new CGI::FastTemplate($config->{templates});
	$tpr->strict();
	$tpr->define( row => "adm_zap/adm_zap_m101112_row.template",
		      url => "common/zap_url.template");
	$tpr->assign($h);
	$tpr->parse("URL", "url");
	$tpr->parse(MAIN => "row");
	$tpr->print("MAIN");

    }
    do_footer_234($config);
}

# upload a new file page (separated so we can set the submit page
# differently
sub mode_5 {
    my ($config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    my $buttons = {}; # 
    $tpl->define( header         => "common/header.template",
                  banner         => "common/adm-banner.template",
		  buttons        => "adm_zap/adm_zap_file_upload.template",
	);
    my %hdr_h =(  Pagename       => 'Upload Zapatista Coffee Product File',
		  Title          => 'Upload Zapatista Coffee Product File',
		  Nextcgi        => 'adm_do_zap_upload.cgi',
		  mem_name       => $config->{mem_name},
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "buttons");
    admin_banner($status, "BANNER", "banner", $tpl, $config);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    print '</form></body></html>';
    exit 0;
}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    get_cats(\%categories, \%cat_descs, \%sc_descs, $dbh);
    open_spreadsheet($config, $cgi, $dbh);
    my $new_vals = get_vars($config, $cgi, $dbh);

    my ($voko_changed, $voko_dropped, $voko_same, 
	    $new_zap, $zap_maybe, $zap_all) = 
		get_stats($new_vals, $config, $cgi, $dbh);
    
    get_choice($voko_changed, $voko_dropped, $voko_same, 
	       $new_zap, $zap_maybe, $zap_all, $config, $cgi, $dbh) 
	if(not $config->{choice});
    mode_1($voko_changed, $voko_dropped, $config, $cgi, $dbh)
	if($config->{choice} == 1);
    mode_2($new_vals, $new_zap, $config, $cgi, $dbh) 
	if(($config->{choice} & ~8) == 2);
    mode_3($new_vals, $zap_maybe, $config, $cgi, $dbh) 
	if(($config->{choice} & ~8) == 3);
    mode_4($new_vals, $zap_all, $config, $cgi, $dbh) 
	if(($config->{choice} & ~8)== 4);
    mode_5($config, $cgi, $dbh) if($config->{choice} == 5);
}
    

sub main {
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);
    $config->{nextcgi}  = "adm_zap.cgi";
    $config->{title}    = "Process Zapatista Coffee Product List";
    $config->{choice} = 0;

    openlog( $program, LOG_PID, LOG_USER );

    my ($cgi, $dbh) = open_cgi($config);
    if($program =~ /login/) {
	process_login(1, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    my $sth = prepare('SELECT ord_no, ord_status FROM order_header', $dbh);
    $sth->execute;
    my $aref = $sth->fetchrow_arrayref;
    if(not defined($aref)) {
	die "Could not get order no and status";
    }
    $sth->finish;

    ($ord_no, $status) = @{$aref};

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
