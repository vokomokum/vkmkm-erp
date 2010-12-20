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

sub get_vars {
    my ($vals, $config, $cgi) = @_;
    my %parse_hash;

    foreach my $k (qw( cat_id cat_name sc_id  sc_name sc_desc)) {
	$parse_hash{$k} = "";
    }

    foreach my $k (keys %{$vals}) {
	my $v = $vals->{$k};
	$v =~ s/^\s*//;
	$v =~ s/\s+$//;
	if($k eq "Menu") {
	    next if($v !~ /^(-?\d+)/);
	    $vals->{cat_id} = $1;
	}
	if($k eq "SC_Menu") {
	    next if($v !~ /^(-?\d+)/);
	    $vals->{sc_id} = $1;
	}
	$parse_hash{$k} = escapeHTML($v);
    }
    return \%parse_hash;
}

# get the category of interest
sub pass0 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  hidden      => "edit_subcat/hidden.template",
	);
    my %hdr_h =(  Pagename    => "Select Category for Edit/Create Sub-Categories",
		  Title       => "Select Category for Edit/Create Sub-Categories",
		  Nextcgi     => "edit_subcat.cgi",
		  mem_name    => $config->{mem_name},
		  cat_id      => -1,
		  cat_name    => "",
		  sc_id       => -1,
		  sc_name     => "",
		  sc_desc     => "",
		  pass        => 1,
	);


    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "<span class=\"warn\"><big>$err_msgs</big></span>" 
	if(length($err_msgs) > 0); 

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( body    => "edit_subcat/select_cat.template",
                  row     => "edit_subcat/cat_row.template",
		  footer  => "common/editcat_ftr.template",
	);

    # get a list of categories for a drop down menu
    my $cmd = "SELECT cat_id, cat_name FROM category ORDER BY cat_id";
    my $sth = prepare($cmd, $dbh);
    $sth->execute;
    while(my $h = $sth->fetchrow_hashref) {
	$tpl->assign({ catid   => $h->{cat_id},
		       cat_name => escapeHTML($h->{cat_name}),
		     });
	$tpl->parse( ROWS => ".row");
	$tpl->clear_href(1);
    }
    $sth->finish;
    $tpl->parse(FOOTER => "footer");
    $tpl->parse(MAIN   => "body");
    $tpl->print("MAIN");
    $dbh->disconnect;
    exit 0;
}

# come here when category selected from list (we hope)
sub pass1 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass0($parse_hash, $vals, $config, $cgi, $dbh) 
	if(not defined($vals->{cat_id}) or $vals->{cat_id} < 0);
    
    $parse_hash->{cat_name} = $vals->{cat_name} = "";

    my $cmd = "SELECT * FROM category WHERE cat_id = ?";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($vals->{cat_id});
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    $vals->{cat_name} = $h->{cat_name};
    $parse_hash->{cat_name} = escapeHTML($vals->{cat_name});

    pass2($parse_hash, $vals, $config, $cgi, $dbh);

}

# we have a category, now list the subcategories that are available
# special cases are 0 (return to category select) and 1
# create a new sub-category

sub pass2 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  hidden      => "edit_subcat/hidden.template",
	);

    my %hdr_h =(  pass        => 3,
		  Pagename    => "Select Sub-Category to Edit/Create",
		  Title       => "Select Sub-Category to Edit/Create",
		  Nextcgi     => "edit_subcat.cgi",
		  mem_name    => $config->{mem_name},
		  cat_id      => $vals->{cat_id},
		  cat_name    => $parse_hash->{cat_name},
		  sc_id       => 0,
		  sc_name     => "",
		  sc_desc     => "",
		  
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "<span class=\"warn\"><big>$err_msgs</big></span>" 
	if(length($err_msgs) > 0); 

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( body    => "edit_subcat/select_subcat.template",
                  row     => "edit_subcat/subcat_row.template",
		  footer  => "common/editcat_ftr.template",
	);

    $tpl->assign( {cat_name    => $parse_hash->{cat_name}} );
    
    # get a list of sub-categories for a drop down menu
    my $cmd = "SELECT sc_id, sc_name FROM sub_cat WHERE cat_id = ? ".
	"ORDER BY sc_name";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($vals->{cat_id});
    while(my $h = $sth->fetchrow_hashref) {
	$tpl->assign({ sc_id   => $h->{sc_id},
		       sc_name => escapeHTML($h->{sc_name}),
		     });
	$tpl->parse( ROWS => ".row");
	$tpl->clear_href(1);
    }
    $sth->finish;
    $tpl->parse(FOOTER => "footer");
    $tpl->parse(MAIN   => "body");
    $tpl->print("MAIN");
    $dbh->disconnect;
    exit 0;
}

# come here when a sub-category has been selected
sub pass3 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass0($parse_hash, $vals, $config, $cgi, $dbh) 
	if(not defined($vals->{sc_id}) or $vals->{sc_id} <= 0);
    
    # they want to create a new one
    if($vals->{sc_id} == 1) {
	$parse_hash->{sc_name} = $parse_hash->{sc_desc} = "";
	$vals->{sc_name} = $vals->{sc_desc} = "";
	pass4(6, $parse_hash, $vals, $config, $cgi, $dbh);
    }

    my $cmd = "SELECT * FROM sub_cat WHERE cat_id = ? AND sc_id = ?";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($vals->{cat_id}, $vals->{sc_id});
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    $vals->{sc_name} = $h->{sc_name};
    $vals->{sc_desc} = $h->{sc_desc};
    $parse_hash->{sc_name} = escapeHTML($vals->{sc_name});
    $parse_hash->{sc_desc} = escapeHTML($vals->{sc_desc});

    pass4(5, $parse_hash, $vals, $config, $cgi, $dbh);
}


sub pass4 {
    my ($next_pass, $parse_hash, $vals, $config, $cgi, $dbh) = @_;

    $dbh->disconnect;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
          hidden      => "edit_subcat/hidden.template",
	);

    my %hdr_h =(  Pagename    => ($next_pass == 5) ?
		      "Edit Syb-Category of $parse_hash->{cat_name}" : 
		      "Create Sub-Category of $parse_hash->{cat_name}",
		  Title       => ($next_pass == 5) ?
		      "Edit Syb-Category of $parse_hash->{cat_name}" : 
		      "Create Sub-Category of $parse_hash->{cat_name}",
		  Nextcgi     => "edit_subcat.cgi",
		  mem_name    => $config->{mem_name},
		  cat_id      => $vals->{cat_id},
		  cat_name    => $vals->{cat_name},
		  sc_id       => $vals->{sc_id},
		  sc_name     => $vals->{sc_name},
		  sc_desc     => $vals->{sc_desv},
		  pass        => $next_pass,
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(BUTTONS => "hidden");
    admin_banner($status, "BANNER", "banner", $tpl, $config);

    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");

    print "<span class=\"warn\"><big>$err_msgs</big></span>" 
	if(length($err_msgs) > 0); 

    $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( body        => "edit_subcat/body.template",	);
    $tpl->assign({cat_name => $parse_hash->{cat_name},
		  sc_name  => $parse_hash->{sc_name},
		  sc_desc  => $parse_hash->{sc_desc},
		  edit     => ($next_pass == 5) ?
		      "Update" : "Create",
		 });
    $tpl->parse(MAIN => "body");
    $tpl->print("MAIN");
    exit 0;
}


# User update input available, check and update
sub pass5 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $cmd = "UPDATE sub_cat SET sc_name = ?, sc_desc = ? " .
	"WHERE cat_id = ? AND sc_id = ?";
    #dump_stuff("pass5", "", "", \$cmd);
    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute($vals->{sc_name}, $vals->{sc_desc}, $vals->{cat_id},
	    $vals->{sc_id});
    };
    if($@) {
	$err_msgs .= sprintf "<p>%s</p>", $dbh->errstr;
	$dbh->rollback;
    } else {
	$err_msgs .= "<p>Updated sub-category $parse_hash->{sc_name}</p>";
	$dbh->commit;
    }
    pass2($parse_hash, $vals, $config, $cgi, $dbh);
}

# User insert input available, check and insert
sub pass6 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass2($parse_hash, $vals, $config, $cgi, $dbh) if($vals->{sc_name} eq "");

    my $cmd = "INSERT INTO sub_cat (sc_active, sc_name, sc_desc, cat_id) " .
	"VALUES(?, ?, ?, ?)";

    #dump_stuff("pass6", "", "", \$cmd);
    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute(1, $vals->{sc_name}, $vals->{sc_desc}, $vals->{cat_id});
    };
    if($@) {
	if($dbh->errstr =~ /idx_sub_cat_name/) {
	    $err_msgs .= "<p>The sub-category name $parse_hash->{sc_name} already exists</p>";
	} else {
	    $err_msgs .= sprintf "<p>%s</p>", $dbh->errstr;
	}
	$dbh->rollback;
    } else {
	$dbh->commit;
	#dump_stuff("pass6", $parse_hash->{sc_name}, $vals->{sc_name}, {});
	$err_msgs .= "<p>Created sub-category $parse_hash->{sc_name}</p>";
    }

    pass2($parse_hash, $vals, $config, $cgi, $dbh);

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    #dump_stuff("doit", "before", "", $vals);
    my $parse_hash = get_vars($vals, $config, $cgi, $dbh);
    #dump_stuff("doit", "after", "", $vals);
    #dump_stuff("doit", "parse_hash", "", $parse_hash);

    pass6($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 6);
    pass5($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 5);
    pass1($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 1);
    pass3($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 3);
    pass0($parse_hash, $vals, $config, $cgi, $dbh);

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
	$mem_id = process_login(1, $config, $cgi, $dbh); 
    } else {
	$mem_id = handle_cookie(1, $config, $cgi, $dbh);
    }

    doit($config, $cgi, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
