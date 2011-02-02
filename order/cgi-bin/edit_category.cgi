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

    foreach my $k (qw( cat_id cat_name cat_desc cat_active)) {
	$parse_hash{$k} = "";
    }
    #dump_stuff("get_vars", "", "", $vals);

    foreach my $k (keys %{$vals}) {
	my $v = $vals->{$k};
	$v =~ s/^\s*//;
	$v =~ s/\s+$//;
	if($k eq "Menu") {
	    next if($v !~ /^(\d+)/);
	    $vals->{cat_id} = $1;
	}
	$parse_hash{$k} = escapeHTML($v);
    }
    return \%parse_hash;
}

sub pass0 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  hidden      => "edit_category/editcat-hidden.template",
	);
    my %hdr_h =(  Pagename    => "Select Category to Edit/Create",
		  Title       => "Select Category to Edit/Create",
		  Nextcgi     => "edit_category.cgi",
		  mem_name    => $config->{mem_name},
		  cat_id      => -1,
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
    $tpl->define( body    => "edit_category/editcat_select.template",
                  row     => "edit_category/editcat_row.template",
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

# setup for edit/create, display current vals if any
sub pass1 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass0($parse_hash, $vals, $config, $cgi, $dbh) 
	if(not defined($vals->{cat_id}) or $vals->{cat_id} < 0);
    
    $parse_hash->{cat_name} = $vals->{cat_name} = "";
    $parse_hash->{cat_desc} = $vals->{cat_desc} = "";
    pass2(4, $parse_hash, $vals, $config, $cgi, $dbh) if($vals->{cat_id} == 0);
    my $cmd = "SELECT * FROM category WHERE cat_id = ?";
    my $sth = prepare($cmd, $dbh);
    $sth->execute($vals->{cat_id});
    my $h = $sth->fetchrow_hashref;
    $sth->finish;
    $vals->{cat_name} = $h->{cat_name};
    $vals->{cat_desc} = $h->{cat_desc};
    $parse_hash->{cat_name} = escapeHTML($vals->{cat_name});
    $parse_hash->{cat_desc} = escapeHTML($vals->{cat_desc});

    pass2(3, $parse_hash, $vals, $config, $cgi, $dbh);

}

sub pass2 {
    my ($next_pass, $parse_hash, $vals, $config, $cgi, $dbh) = @_;

    $dbh->disconnect;

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
                  banner      => "common/adm-banner.template",
		  hidden      => "edit_category/editcat-hidden.template",
	);
    my %hdr_h =(  Pagename    => ($next_pass == 3) ?
		  "Edit Category" : "Create Category",
		  Title       => ($next_pass == 3) ?
		  "Edit Category" : "Create Category",
		  Nextcgi     => "edit_category.cgi",
		  mem_name    => $config->{mem_name},
		  cat_id      => $vals->{cat_id},
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
    $tpl->define( body        => "edit_category/editcat-body.template",
	);
    $tpl->assign({cat_name => $parse_hash->{cat_name},
		  cat_desc => $parse_hash->{cat_desc},
		  edit     => ($next_pass == 3) ?
		      "Update" : "Create",
		 });
    $tpl->parse(MAIN => "body");
    $tpl->print("MAIN");
    exit 0;
}

# User input available, check and update
sub pass3 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    my $cmd = "UPDATE category SET cat_name = ?, cat_desc = ? " .
	"WHERE cat_id = ?";
    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute($vals->{cat_name}, $vals->{cat_desc}, $vals->{cat_id});
    };
    if($@) {
	$err_msgs .= sprintf "<p>%s</p>", $dbh->errstr;
	$dbh->rollback;
    } else {
	$err_msgs .= "<p>Updated category $parse_hash->{cat_name}</p>";
	$dbh->commit;
    }
    pass0($parse_hash, $vals, $config, $cgi, $dbh);
}

# User input available, check and insert
sub pass4 {
    my ($parse_hash, $vals, $config, $cgi, $dbh) = @_;

    pass1($parse_hash, $vals, $config, $cgi, $dbh) if($vals->{cat_name} eq "");

    my $cmd = "INSERT INTO  category (cat_name, cat_desc) VALUES( ?, ?)";
    my $sth = prepare($cmd, $dbh);
    eval {
	$sth->execute($vals->{cat_name}, $vals->{cat_desc});
    };
    if($@) {
	if($dbh->errstr =~ /idx_cat_name/) {
	    $err_msgs .= "<p>The category name $parse_hash->{vat_name} already exists</p>";
	} else {
	    $err_msgs .= sprintf "<p>%s</p>", $dbh->errstr;
	    $dbh->rollback;
	}
    } else {
	$dbh->commit;
	$err_msgs .= "<p>Created category $parse_hash->{cat_name}</p>";
	eval {
	    $cmd = "SELECT currval('category_cat_id_seq')";
	    $sth = prepare($cmd, $dbh);
	    $sth->execute;
	    my $aref = $sth->fetchrow_arrayref;
	    if(defined($aref)) {
		$cmd = "INSERT INTO sub_cat (sc_id, cat_id, sc_name, sc_desc) VALUES (99999, ?, '~Overigen~', '')";
		$sth = prepare($cmd, $dbh);
		$sth->execute($aref->[0]);
	    }
	};
	if(not $@) {
	    $dbh->commit;
	} else {
	    $dbh->rollback;
	}
    }

    pass1($parse_hash, $vals, $config, $cgi, $dbh);

}

sub doit {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my $parse_hash = get_vars($vals, $config, $cgi, $dbh);
    #dump_stuff("edit cat", "parse_hash", "", $parse_hash);
    pass3($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 3);
    pass4($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 4);
    pass1($parse_hash, $vals, $config, $cgi, $dbh) 
	if(defined($vals->{pass}) and $vals->{pass} == 1);
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
