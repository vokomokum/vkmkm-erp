#!/usr/bin/perl

# --------------------------------------
# This script shows who ordered a given product
# --------------------------------------

package voko;
use strict;
use warnings;

use Config::General;
use Data::Dumper;
use DBI;
use CGI::FastTemplate;
use CGI::Pretty qw(:standard);
use CGI qw/escape unescape/;
use CGI::Carp 'fatalsToBrowser';
use Unix::Syslog qw( :macros :subs );
use POSIX qw(strftime);
use MIME::Base64;
use Crypt::PasswdMD5;
use voko;

BEGIN {
    use Exporter   ();
    our ($VERSION, @ISA, @EXPORT, @EXPORT_OK, %EXPORT_TAGS);

    $VERSION     = sprintf "%d.%03d", q$Revision: 1.2 $ =~ /(\d+)/g;

    @ISA         = qw(Exporter);
    @EXPORT      = qw(get_orderers);
    %EXPORT_TAGS = ( );     # eg: TAG => [ qw!name1 name2! ],
    @EXPORT_OK   = ();
}
our @EXPORT_OK;



# get a list of orderers for a product code. If we get a non-negative
# wholesaler number, the lookup is by wholesaler product code, if it's
# negative, the lookup is by vokomokum product code
# returns product description, hash of member name and qty keyed by mem_id 
sub get_orderers {
    my ($config, $dbh, $product_id, $wh_no) = @_;
    my $prod_name = "";
    my %orderers;
    my $mem_names = mem_names_hash($dbh);
    my ($sh_st, $sh_sth);

    if($wh_no < 0) {
	$sh_st = 
	    'SELECT * FROM mo_view WHERE ord_no = ? AND pr_id = ?'; 
	$sh_sth = prepare($sh_st, $dbh);
	$sh_sth->execute($config->{ord_no}, $product_id);
    } else {
	$sh_st = 
	    'SELECT * FROM mo_view WHERE ord_no = ? AND wh_prodno = ? '.
	    'AND wh_no = ?'; 
	$sh_sth = prepare($sh_st, $dbh);
	$sh_sth->execute($config->{ord_no}, $product_id, $wh_no);
    }
    while(my $row = $sh_sth->fetchrow_hashref) {
        $prod_name = $row->{descr};
	my $mem_id = $row->{mem_id};
        my %data = ();
        $data{mem_name} = $mem_names->{$mem_id};
        $data{qty} = $row->{qty};
	$orderers{$mem_id} = \%data;
    }
    $sh_sth->finish;
    $dbh->commit;
    return ($prod_name, \%orderers);
}

# return a dropdown wholesaler list with a default of 'Vokomokum product"
sub get_wholesalers {
    my ($config, $dbh) = @_;

    my $res = '<select name="WhID", id="WhID">\n' .
	'<option selected value="-1">Vokomokum product code</option>\n';

    my $st = 'SELECT wh_id, wh_name FROM wholesaler WHERE wh_active ORDER BY wh_name';
    my $sth = prepare($st, $dbh);
    $sth->execute;
    while(my $h = $sth->fetchrow_hashref) {
	$res .= sprintf('<option value="%d">%s product code</option>'.'\n',
			$h->{wh_id}, escapeHTML($h->{wh_name}));
    }
    $sth->finish;
    $dbh->commit;
    return $res . "</select>\n";
}

sub write_form {
    my ($config, $dbh) = @_;

    my $tpl = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();
    $tpl->define(header => "common/header.template",
		 banner => (( $config->{is_admin} )
		 ? "common/adm-banner.template"
		 : "common/mem-banner.template"),
		 prbuttons => "who_ordered/buttons.template",
		 subtitle => $config->{subtitle}
	);
    my $title = "Who ordered this product?";
    my $nextcgi = "/cgi-bin/who_ordered.pm";
    my %hdr_h = (
	Pagename    => $title,
	Title	    => $title,
	Nextcgi	    => $nextcgi,
	mem_name    => $config->{mem_name},
	WHOLESALERS => get_wholesalers($config, $dbh),
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse( BUTTONS => "prbuttons" );
    admin_banner($config->{status}, "BANNER", "banner", $tpl, $config);
    $tpl->parse( MAIN => "header" );
    $tpl->print( "MAIN" );
}

# list orderers
sub show_orderers{
    my ($config, $dbh, $product_id, $wh_no) = @_;

    write_form($config, $dbh);

    if ($product_id == ''){
        return;
    }

    my ($prod_name, $dict) = 
	get_orderers($config, $dbh, $product_id, $wh_no);
    
    my %orderers = %{$dict};
    return if(scalar(keys(%orderers)) == 0);
    my $tpl = new CGI::FastTemplate( $config->{templates} );
    $tpl->strict();

    $tpl->define(header => "who_ordered/who_ordered_table.template",
		 row    => ($config->{is_admin}) ? 
		 "who_ordered/who_ordered_admrow.template":
		 "who_ordered/who_ordered_memrow.template",
	);

    # loop through all members
    for my $orderer ( keys %orderers ) {
	$tpl->assign( {
	    ord_no   => $config->{ord_no},
	    onr      => $orderer,
	    mem_name => escapeHTML($orderers{$orderer}->{mem_name}),
	    qty      => $orderers{$orderer}->{qty},
		      } );
	$tpl->parse(ROWS => ".row");
	$tpl->clear_href(1);
    } 
    $tpl->assign( {product_id => $product_id, 
		   prod_name => escapeHTML($prod_name)
		  });
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
}

sub get_button {
    my ($config, $cgi, $dbh) = @_;
    my $vals = $cgi->Vars;
    my %buttons;

    # copy the buttons 
    $buttons{ProtID} = '';
    $buttons{WhID} = -1;

    foreach my $but ( qw( ProdID WhID)) {
	if (defined($vals->{$but})) {
	    $buttons{$but} = $vals->{$but};
	}
    }

    return \%buttons;
}


# --------- copied from some other module, we might not need all of this 
# globals to make everyone's life easier
my $mem_id;
my $conf = "../passwords/db.conf";
sub main {	     
    my $program = $0;
    $program =~ s/.*\///;
    syslog(LOG_ERR, "$program");
    my $config = read_conf($conf);

    $config->{caller} = $program if($program !~ /login/);
    $config->{program} = $program;
    my @stuff = localtime(time + 21 * 86400);
    $config->{order_name} = strftime("%d %B %Y", @stuff);

    openlog( $program, LOG_PID, LOG_USER );
    syslog(LOG_ERR, "Running as $program");

    my ($cgi, $dbh) = open_cgi($config);
    #($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	process_login(0, $config, $cgi, $dbh); 
    } else {
	handle_cookie(0, $config, $cgi, $dbh);
    }

    my $button = get_button($config, $cgi, $dbh);    
    show_orderers($config, $dbh, $button->{ProdID}, $button->{WhID});

    print "</form>\n</body>\n</html>\n";

    $dbh->disconnect;
    exit 0;

}
main;
# -----------

END { }       # module clean-up code here (global destructor)
1;
