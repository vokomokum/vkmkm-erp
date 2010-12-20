#!/usr/bin/perl

# --------------------------------------
# Call this script to generate pickup lists
# (in your browsaer and for our files)
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
    @EXPORT      = qw(print_pickup_lists);
    %EXPORT_TAGS = ( );     # eg: TAG => [ qw!name1 name2! ],
    @EXPORT_OK   = ();
}
our @EXPORT_OK;



# this prints and saves an HTML file in data/pick_lists called 
# <year>-<month>-<day>.html with all pickup lists for the day it is run
sub print_pickup_lists{
    my ($config, $dbh) = @_;

    # we believe this many lines can fit vertically on DIN A4, scaled 50%
    my $line_limit_vertical = 60;
    my $base_lines = 2; # we're always starting with two headlines

    # check if actually the order status is 7 (order finished, invoices can be prepared)
    if ($config->{status} != 7){
        print "I will not make pickup lists, since the order status is not 7 (order finished, invoices can be prepared), but $config->{status}";
        return;
    }

    my $date = getDate();
    my $filename = "$date.html";
    my $list = '';    
    $list .= "<html>
    <head>
        <meta http-equiv='content-type' content='text/html; charset=utf-8' />
        <style>
        .pickup-list {
            float: left;
            width: 45%;
            min-height: 695pt; /*best fit for half a page height for me in */
            padding: 2%;       /* FF at 50% print preview*/
            border: 1px solid black;
        }
        .pickup-head {
            margin-bottom: 4px;
            color: #fff;
            background-color: #333;
            padding: 2px;
        }
        .pickup-table thead td { 
            border-bottom: 1px solid #aaa;
            font-weight: bold;
            text-align: center;
        }
        .even-row td {
            background-color: #ccc;
        }
        .qty_col{
            text-align: center;
        }
        .eur_col{
            text-align: right;
        }
        .res_col { 
            border-top: 1px solid #333; 
            font-weight: bold;
        }
        .lesser{
            color: #333;
        }

        /* page breaks */
        .page-break {
            clear: all;
            height: 0px;
        }
        \@media print {
            .page-break {
                page-break-before: always;
            }
        }
        </style>
    </head>
";
    
    $list .= "\t<body>\n";
   
    # find members and the number of their order items we need to list
    my $st = 'SELECT m.mem_id, join_name(m.mem_fname, m.mem_prefix, '.
        'm.mem_lname) as mem_name, 10 + COUNT(*) as amount FROM members m, '.
        'mem_line ml WHERE ml.ord_no = ? AND m.mem_id = ml.mem_id '.
        'AND ml.meml_pickup > 0 '.
        'GROUP BY m.mem_id, m.mem_fname, m.mem_prefix, m.mem_lname '.
        'ORDER BY amount DESC ';
    my $sth = prepare($st, $dbh);
    $sth->execute($config->{ord_no});
    my $lists_on_page = 0;
    my $lines_on_page = $base_lines;
    my $max_lists_per_page = 1;
    my $new_page = 1;
    # loop through all members
    while(my $mem = $sth->fetchrow_hashref) {
	my $amount = $mem->{amount};
        # maximal orders on one page, not too many lines
        if($lists_on_page >= $max_lists_per_page || 
	    ($lines_on_page + $amount) > 2 * $line_limit_vertical){ 
            $list .= "\t\t<hr class='page-break'/>\n";
            $lists_on_page = 0;       
            $lines_on_page = $base_lines;       
	    $new_page = 1;
        }

	if($new_page) {
	    # only set list limit on the first list of a page
	    $max_lists_per_page = 4;
	    # +10 so the footer (result and notes etc.) still fits 
	    # (could be done better)
	    if ($amount > $line_limit_vertical/2){
		$max_lists_per_page = 2;
	    }
	    if ($amount > $line_limit_vertical){
		$max_lists_per_page = 1;
	    }
	    $new_page = 0;
        }

        my $st = 'SELECT ml.mem_id, p.pr_desc, ml.meml_rcv, '.
	    'ml.meml_unit_price, ml.meml_btw FROM members m, '.
	    'mem_line ml, product p WHERE ml.ord_no = ? AND '.
	    'm.mem_id = ml.mem_id AND m.mem_id = ? AND ml.pr_id = p.pr_id '.
            'AND ml.meml_rcv > 0';
        my $sth2 = prepare($st, $dbh);
        $sth2->execute($config->{ord_no}, $mem->{mem_id});
        $list .= tableHead(1, $mem, $date);
        $lines_on_page++;       
        my $sum_prices = 0;
        my $sum_btw = 0;
        
        # loop through all the ordered products
        while(my $o = $sth2->fetchrow_hashref) {
            # all EUR numbers are carried in cents (as in the DB), 
	    # for printing only we divide by 100
            my $pr = $o->{meml_rcv} * $o->{meml_unit_price};
            $sum_prices += $pr;
	    # the unit prices are inclusive btw
            my @full_eur = ($o->{meml_unit_price}/100, $pr/100);

            # cutting out everything after "(x per": the description 
	    # how many to order, show only x
            $o->{pr_desc} =~ s/(.*)(\([^{]*)/$1/;
	    $o->{pr_desc} = sprintf("%-47.47s", $o->{pr_desc});
            my $tr_class = '';
            if ($lines_on_page % 2 == 0){
                $tr_class = " class='even-row'";
            }
            $list .= sprintf "\t\t\t\t<tr$tr_class><td>%s</td><td class='qty_col'>%d</td><td class='eur_col lesser'>%.2f</td><td class='eur_col'>%.2f</td></tr>\n", 
                             $o->{pr_desc}, $o->{meml_rcv}, $full_eur[0], $full_eur[1];
            $lines_on_page++;        
            # new column? only when we are still in our first on this page 
            # and run out of vertical space
            if($lists_on_page == 0 && $lines_on_page == $line_limit_vertical){
                $list .= "\t\t\t</table>\n";
                $list .= "\t\t</div>\n";
                $list .= tableHead(0, $mem, $date);
            }
	}
        $list .= "\t\t\t\t<tr><td colspan='5'/></tr>\n";
        my @full_eur = ($sum_prices/100, $sum_btw/100);

        #my $sth3 = prepare("select total_inc_btw(?, ?);", $dbh);
        #$sth3->execute($mem->{mem_id}, $config->{ord_no});
        #my $row = $sth3->fetchrow_hashref;
	$list .= sprintf "\t\t\t\t<tr><td colspan='3'/><td class='res_col eur_col'>%.2f</td></tr>\n", $full_eur[0];
        #$list .= "\t\t\t\t<tr><td>incl. BTW:</td><td>$row->{total_inc_btw}</td><td colspan="2"/></tr>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>Statiegeld:</td><td/></tr>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>&nbsp;</td><td class='res_col'>&nbsp;</td></tr>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>Retour:</td></tr><td/>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>&nbsp;</td><td class='res_col'>&nbsp;</td></tr>\n";
        $list .= "\t\t\t\t<tr><td colspan='4'>Notes:</td></tr>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>&nbsp;</td></tr>\n";
        $list .= "\t\t\t\t<tr><td/><td colspan='2'>&nbsp;</td></tr>\n";
        $lines_on_page += 8;       
        $sth2->finish;
        $list .= "\t\t\t</table>\n";
        $list .= "\t\t</div>\n";
        $lists_on_page++;        
    } 
    $sth->finish;
    
    $list .= "\t</body>\n";
    $list .= "</html>\n";
    
    # done, print to both file and output
    open(my $list_file, ">",  "../data/pick_lists/$filename")  
        or die "Cannot open $filename for writing: $!";
    print $list_file $list;
    close $list_file or die "$list_file: $!";
    return $list;
}

# call with $list and $is_first and $mem (hash), date string
sub tableHead {
    my ($is_first, $mem, $date)  = @_;
    my $out = "\t\t<div class='pickup-list'>\n";
    if ($is_first) {
        my $date = getDate();
        $out .= sprintf "\t\t\t<div class='pickup-head'>Vokomokum Pickup for %s (# %d) - %s</div>\n", 
	$mem->{mem_name}, $mem->{mem_id}, $date;
    }else{
        $out .= "\t\t\t<br/>\n";
    }
    $out .= "\t\t\t<table class='pickup-table'>\n";
    $out .= "\t\t\t\t<thead class='pickup-table-head'><td>Product</td><td>Quantity</td><td class='lesser'>Price</td><td>Sum</td></thead>\n";
}

# return day-month-year as a string
sub getDate {
    my ($sec,$min,$hour,$mday,$month,$year,$wday,$yday,$isdst) = 
	localtime(time);
    return sprintf "%d-%d-%4d", $mday, $month+1, $year+1900;
}


# --------- copied from some other module, we might not need all of this 
# globals to make everyone's life easier
my $mem_id;
my $ord_no;
my $status;
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
    ($status, $ord_no) = ($config->{status}, $config->{ord_no});

    if($program =~ /login/) {
	process_login(1, $config, $cgi, $dbh); 
    } else {
	handle_cookie(1, $config, $cgi, $dbh);
    }

    print "Content-type: text/html\n\n";
    print print_pickup_lists($config, $dbh);

    $dbh->disconnect;
    exit 0;

}
main;
# -----------

END { }       # module clean-up code here (global destructor)
1;
