# $Id: voko.pm,v 1.2 2010/04/13 06:19:46 jes Exp jes $

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

BEGIN {
    use Exporter   ();
    our ($VERSION, @ISA, @EXPORT, @EXPORT_OK, %EXPORT_TAGS);

    $VERSION     = sprintf "%d.%03d", q$Revision: 1.2 $ =~ /(\d+)/g;

    @ISA         = qw(Exporter);
    @EXPORT      = qw(read_conf connect_database prepare set_cookie
                      process_login force_login print_title handle_cookie
                      admin_banner test_cookie process_login_data open_cgi
                      password_reset get_cats order_selector print_sub_cat
		      mem_names_hash make_dropdown make_scdrop email_header
		      email_chunk email_rows get_ord_totals dump_stuff);
    %EXPORT_TAGS = ( );     # eg: TAG => [ qw!name1 name2! ],
    @EXPORT_OK   = ();
}
our @EXPORT_OK;

sub read_conf {
    my ($conf) = @_;
    my %config;
    my $cnf = new Config::General("$conf")
	or die "Can't read config file $conf";
    
    %config = $cnf->getall;
    return \%config;
}

sub connect_database {
    my ($config) = @_;

    my $req = "dbi:Pg:dbname=$config->{dbase_name};" .
	"host=$config->{dbase_server}";
    my $dbh = DBI->connect( "$req", $config->{get_prod}->{dbase_user},
			    $config->{get_prod}->{dbase_password}, 
			    { RaiseError => 1, AutoCommit => 0 } );
    die "connect: $req failed: DBI::errstr" if not $dbh;
    return $dbh;
}

sub prepare {
    my($st, $dbh) = @_;

    my $sth = $dbh->prepare($st);
    return $sth if($sth);
    my($package, $filename, $line) = caller;
    die "$filename:$line dbh->prepare failed, $dbh->errstr";
}

sub set_cookie {
    my ($mem_id, $config, $cgi, $dbh) = @_;

    # generate a big random number
    open(RND, "</dev/random");
    my $buf;
    sysread RND, $buf, 24;
    close(RND);
    my $key = encode_base64($buf);
    chomp $key;

    # record it in the member record
    my $sth = prepare(
	"UPDATE members SET mem_cookie = ?, mem_ip = ? WHERE mem_id = ?", $dbh);
    $sth->execute($key, $ENV{REMOTE_ADDR}, $mem_id);
    $dbh->commit;
    my $tpl = new CGI;
    my $cookiem = $cgi->cookie(-name =>'Mem',
                    -value => $mem_id,
		    -path=>'/',
		    -expires=>'+1y',
                    -secure=>0);


    my $cookiek = $cgi->cookie(-name =>'Key',
                    -value => $key,
		    -path=>'/',
		    -expires=>'+1y',
                    -secure=>0);

    my $cookie = sprintf "%s", $cgi->header(-cookie=>[$cookiem, $cookiek]);
    map {print "$_\n" if($_ =~ /^Set-Cookie/);} split(/[\r\n]+/, $cookie);
}

sub force_login {
    my ($config, $cgi, $dbh) = @_;
    $dbh->disconnect;
    my $adm = (($config->{caller} =~ /adm/) or 
	       ($config->{program} =~ /adm/));
    my $title = ($adm) ?
	'Vokomokum Administrator Login' : 'Vokomokum Member Login';

    my $next = ($adm) ?
	"/cgi-bin/adm-login" : "/cgi-bin/welcome.cgi";

    my $has_cookie = $cgi->raw_cookie();
    my %h = (Pagename => $title,
	     Title    => $title,
	     Caller   => "/cgi-bin/" . "$config->{caller}",
             Nextcgi  => $next,
	     err_msgs => (defined($has_cookie)) ?
	     "Your login has expired or your last login was from a different".
	     " web browser than your current one, <BR>Please login again" :
	     "",
	);

    my $tpl = new CGI::FastTemplate($config->{templates});
    $tpl->strict();
    $tpl->define( header      => "voko/login_header.template");
    $tpl->assign(\%h);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    exit 0;
}

sub process_login {
    my ($need_adm, $config, $cgi, $dbh) = @_;
    my $mem_id;

    force_login($config, $cgi, $dbh) 
	if (($mem_id = process_login_data($need_adm, $config, $cgi, $dbh) < 0));

    return $mem_id;
}

sub process_login_data {
    my ($need_adm, $config, $cgi, $dbh) = @_;
    my $mem_id;

    my $vals = $cgi->Vars;

    do_forgot($vals, $config, $cgi, $dbh) 
	if(defined($vals->{Member}) and defined($vals->{Forgot}));

    return -5 if(not defined($vals->{Member}) or not defined($vals->{Password}));
    my $memno = $vals->{Member};
    $memno =~ s/^\s*//;
    $memno =~ s/\s*$//;
    
    return -6 if ($memno eq "");
    my $pwd = $vals->{Password};
    $pwd =~ s/^\s*//;
    $pwd =~ s/\s*$//;
    my $sth;
    
    if ( $memno =~ /^\d+$/ ) {
    
        $memno = int($memno);
        $sth =
            prepare(
                'SELECT * FROM members WHERE mem_id = ? AND mem_active',
                $dbh
            );
	    
    } else {
    
	   $memno =~ s/%//;
	   $sth =
	       prepare(
	           'SELECT * FROM members WHERE mem_email ILIKE ? AND mem_active',
	           $dbh
           );
           
    }
    
    $sth->execute( $memno );
    my $href = $sth->fetchrow_hashref;
    $sth->finish;
    
    #dump_stuff("pwd_fail", unix_md5_crypt($pwd, $href->{mem_enc_pwd}),
    #	       $pwd, \$memno);
    return -7 
	if(unix_md5_crypt($pwd, $href->{mem_enc_pwd}) ne $href->{mem_enc_pwd});
    
    $mem_id = $href->{mem_id};
    $config->{mem_name} = 
	escapeHTML(sprintf "%s %s%s",
		   $href->{mem_fname},
		   ((defined($href->{mem_prefix}) and
		     ($href->{mem_prefix} ne '')) ?
		    "$href->{mem_prefix} " : ""),
		   $href->{mem_lname});
    $config->{is_admin} = $href->{mem_admin};
    return -8 if(not $config->{is_admin} and $need_adm);
    # flag if there's a message from the admins for this user
    $config->{has_message} = ($href->{mem_message} !~ /^\s*$/) ? 1 : 0;;
    # see if they've read the latest news item
    $sth = prepare("SELECT news_id from member_news ORDER BY news_id DESC LIMIT 1", 
		   $dbh);
    $sth->execute();
    my $aref = $sth->fetchrow_arrayref;
    $sth->finish;
    $config->{new_news} = ($aref->[0] > $href->{mem_news}) ? 1 : 0;
    set_cookie($mem_id, $config, $cgi, $dbh);
    return $mem_id;
    
}

# print category title bar

sub print_title {
    my ($title, $anchor, $name, $text, $config)  = @_;
    my %h = (cat         => $anchor,
	     Name        => $name,
	     Description => $text),

    my $tplt = new CGI::FastTemplate($config->{templates});
    $tplt->define(title_line => $title);
    $tplt->assign(\%h);
    $tplt->parse(MAIN => "title_line");
    $tplt->print();
    $tplt = undef;
}


sub print_sub_cat {
    my ($title, $cat, $sc, $sc_descs, $config)  = @_;
    
    my %h = (Name        => $sc_descs->{$cat * 100000 + $sc}->{name},);

    my $tplt = new CGI::FastTemplate($config->{templates});
    $tplt->define(title_line => $title);
    $tplt->assign(\%h);
    $tplt->parse(MAIN => "title_line");
    $tplt->print();
    $tplt = undef;
}

# try to get member no, don't worry if it fails
sub test_cookie {
    my ($need_adm, $config, $cgi, $dbh) = @_;
    my $mem_id;
    my $key;
    my $sth;
    my $cookie = unescape($cgi->raw_cookie());

    $config->{mem_name} = "";
    $config->{is_admin} = 0;
    if($cookie =~ /.*Key=([^\s;]*).*/) {
	$key = $1;
    } else {
	return -1;
    }
    if($cookie =~ /.*Mem=([^;]*).*/) {
	$mem_id = int($1);
    } else {
	return -2;
    }
    if($need_adm) {
	$sth = prepare(
	    "SELECT * FROM members WHERE mem_id = ? AND mem_admin", $dbh);
    } else {
	$sth = prepare(
	    "SELECT * FROM members WHERE mem_id = ?", $dbh);
    }
    $sth->execute($mem_id);
    my $href = $sth->fetchrow_hashref;
    $sth->finish;
    if(not defined($href) or not $href->{mem_id}) {
	return -3;
    }
    $href->{mem_cookie} =~ s/^\s*([^\s]*)\s*/$1/ 
	if(defined($href->{mem_cookie}));

    return -4 if(not defined($href->{mem_cookie}) or
		 $href->{mem_cookie} ne $key or 
		 $href->{mem_ip} ne $ENV{REMOTE_ADDR});
    $config->{mem_name} = escapeHTML(sprintf "%s %s%s", 
				     $href->{mem_fname},
				     ((defined($href->{mem_prefix}) and
				      ($href->{mem_prefix} ne '')) ?
				     "$href->{mem_prefix} " : ""),
				     $href->{mem_lname});
    $config->{is_admin} = $href->{mem_admin};
    $config->{is_admin} = $href->{mem_admin};
    return -8 if(not $config->{is_admin} and $need_adm);
    # flag if there's a message from the admins for this user
    $config->{has_message} = ($href->{mem_message} !~ /^\s*$/) ? 1 : 0;
    # see if they've read the latest news item
    $sth = prepare("SELECT news_id from member_news ORDER BY news_id DESC LIMIT 1", 
		   $dbh);
    $sth->execute();
    my $aref = $sth->fetchrow_arrayref;
    $sth->finish;
    $config->{new_news} = ($aref->[0] > $href->{mem_news}) ? 1 : 0;
    return $mem_id;
}

sub handle_cookie {
    my ($need_adm, $config, $cgi, $dbh) = @_;
    my $mem_id;
    my $key;
    my $sth;
    my $cookie = $cgi->raw_cookie();
    #dump_stuff("handle_cookie", $cookie, "", {});
    if($cookie =~ /.*Key=([^\s;]*).*/) {
	$key = unescape($1);
    } else {
	force_login($config, $cgi, $dbh);
    }
    if($cookie =~ /.*Mem=([^;]*).*/) {
	$mem_id = int($1);
    } else {
	force_login($config, $cgi, $dbh);
    }
    if($need_adm) {
	$sth = prepare(
	    "SELECT * FROM members WHERE mem_id = ? AND mem_admin", $dbh);
    } else {
	$sth = prepare(
	    "SELECT * FROM members WHERE mem_id = ?", $dbh);
    }
    $sth->execute($mem_id);
    my $href = $sth->fetchrow_hashref;
    $sth->finish;

    if(not defined($href) or not $href->{mem_id}) {
	$dbh->disconnect;
	die "Don't have administrator account for member number $mem_id";
    }

    $href->{mem_cookie} =~ s/^\s*([^\s]*)\s*/$1/ 
	if(defined($href->{mem_cookie}));

    if(not defined($href->{mem_cookie}) or
       $href->{mem_cookie} ne $key or 
       $href->{mem_ip} ne $ENV{REMOTE_ADDR}) {
	force_login($config, $cgi, $dbh);
    }
    $config->{mem_name} = escapeHTML(sprintf "%s %s%s", 
				     $href->{mem_fname},
				     ((defined($href->{mem_prefix}) and
				      ($href->{mem_prefix} ne '')) ?
				     "$href->{mem_prefix} " : ""),
				     $href->{mem_lname});
    $config->{is_admin} = $href->{mem_admin};
    # flag if there's a message from the admins for this user
    $config->{has_message} = ($href->{mem_message} !~ /^\s*$/) ? 1 : 0;
    # see if they've read the latest news item
    $sth = prepare("SELECT news_id FROM member_news ORDER BY news_id DESC LIMIT 1", 
		   $dbh);
    $sth->execute();
    my $aref = $sth->fetchrow_arrayref;
    $sth->finish;
    $config->{new_news} = ($aref->[0] > $href->{mem_news}) ? 1 : 0;
    return $mem_id;
}


# generate an admin banner appropriate to the status
my @links = (
    [3, "Adjust&nbsp;for&nbsp;order&nbsp;shortages", 6, "Adjust&nbsp;for&nbsp;delivery&nbsp;shortages", -1, "Shortages&nbsp;in&nbsp;current&nbsp;order"],
    [5, "Enter&nbsp;delivery&nbsp;shortages", -1, "View&nbsp;wholesale&nbsp;order"],
);

# choose the correct text for one link, based on current status
sub find_text {
    my ($status, $which) = @_;
    
    my $text;

    my $aref = $links[$which];
    while (my $i = shift @{$aref}) {
	$text = shift @{$aref};
	last if($i < 0);
	last if($i == $status);
    }
    return $text;
}

# generate links at page top for admin. Passed status, field name for template,
# template, FastTemplate object, config hash for news/message

sub admin_banner {
    my ($status, $parse_into, $parse_from, $tpl, $config) = @_;

    my %h = ( shortages => find_text($status, 0),
	      delivery  => find_text($status, 1),
	);
    $h{SUBTITLE} = $config->{"status_$status"};
    $h{message} = ($config->{has_message}) ? "red_bold" : "no_msg";
    $h{news} = ($config->{new_news}) ? "red_bold" : "no_msg";
    $tpl->assign(\%h);
    $tpl->parse( $parse_into => $parse_from);
}

sub open_cgi {
    my ($config) = @_;
    # verify config is complete
    my @must_have = qw(dbase_name dbase_server);
    my @get_prod_must_have = qw(dbase_user dbase_password);

    foreach my $mh ( @must_have ) {
	die "Missing config file general entry $mh" 
	    if( not defined( $config->{$mh}));
    }
    foreach my $mh ( @get_prod_must_have ) {
	die "Missing config file general entry $mh" 
	    if( not defined( $config->{get_prod}->{$mh} ) );
    }

    my $cgi = new CGI;
    my $dbh = connect_database($config);
    my $sth = prepare('SELECT ord_no, ord_status, ord_label '.
		      'FROM order_header', $dbh);
    $sth->execute;
    my $aref = $sth->fetchrow_arrayref;
    if(not defined($aref)) {
        die "Could not get order no and status";
    }
    $sth->finish;
    $config->{ord_no}    = $aref->[0];
    $config->{status}    = $aref->[1];
    $config->{ord_label} = $aref->[2];
    if(defined($config->{ZAPATISTA})) {
	eval {
	    my $sth = prepare("SELECT p.pr_id, w.wh_url FROM product AS p, " .
			      "zapatistadata AS w ".
			      "where p.wh_prcode = w.wh_prcode", $dbh);
	    $sth->execute;
	    while(my $h = $sth->fetchrow_hashref) {
		$config->{ZAPATISTA}->{$h->{pr_id}} = $h->{wh_url};
	    }
	    $sth->finish;
	    $dbh->commit;
	};
    }

    return ($cgi, $dbh);
}

sub password_reset {
    my ($mem_id, $email, $days, $config, $dbh) = @_;
    
    # generate a big random number
    open(RND, "</dev/random");
    my $buf;
    sysread RND, $buf, 24;
    close(RND);
    my $key = encode_base64($buf);
    chomp $key;
    my $url = sprintf "%s:%d", $key, time + 86400 * $days;
    my $sth = prepare(
	"UPDATE members SET mem_pwd_url = ? WHERE mem_id = ?", $dbh);
    $sth->execute($url, $mem_id);
    $dbh->commit;
    my $subject = "You can set a new password on your account";
    my $fh = email_header($email, $subject, $config);
    email_chunk($fh, "pwdreset_txt.template", {key => $key}, $config);
    email_chunk($fh, "sig_txt.tmplate", {}, $config);
    email_chunk($fh, "html_start.template", {}, $config);
    email_chunk($fh, "pwdreset_html.template", {key => $key}, $config);
    email_chunk($fh, "sig_html.tmplate", {}, $config);
    close($fh);
}

sub do_forgot {
    my ($vals, $config, $cgi, $dbh) = @_;
    my $memno = $vals->{Member};
    $memno =~ s/^\s*//;
    $memno =~ s/\s*$//;
    force_login($config, $cgi, $dbh) if($memno eq "");
    my $sth;
    if($memno =~ /^\d+$/) {
	$memno = int($memno);
	$sth = prepare(
	    'SELECT * FROM members WHERE mem_id = ? AND mem_active',
	    $dbh);
    } else {
	$memno =~ s/%//;
	$sth = prepare(
	    'SELECT * FROM members WHERE mem_email ILIKE ? AND mem_active',
	    $dbh);
    }
    $sth->execute($memno);
    my $href = $sth->fetchrow_hashref;
    $sth->finish;
    force_login($config, $cgi, $dbh) if(not defined($href));
    password_reset($href->{mem_id}, $href->{mem_email}, 3, $config, $dbh);
        my $tpl = new CGI::FastTemplate($config->{templates});
    $dbh->commit;
    $dbh->disconnect;
    $tpl->strict();
    $tpl->define( header      => "common/header.template",
	          body        => "voko/reset-requested.template"
	);
    my %hdr_h =(  Pagename    => "Password Reset Requested",
		  Title       => "Password Reset Requested",
		  Nextcgi     => "mem_login",
		  BANNER      => "",
	);

    $tpl->assign(\%hdr_h);
    $tpl->parse(MAIN => "header");
    $tpl->print("MAIN");
    $tpl->parse(BODY => "body");
    $tpl->print("BODY");
    exit 0;
}

# return a list of category links as a single table string
# also creates hashs of cat_no->name, cat_no->description
# finally creates a hash with key = 100000*cat + sub_cat} => 
#   {name=>sc_name, sort=>sort_order}
sub get_cats {
    my ($categories, $cat_descs, $sc_descs, $dbh) = @_;

    my $sth = prepare("SELECT cat_id, cat_name, cat_desc FROM category ".
		      "WHERE cat_active ORDER BY cat_name", $dbh);
    $sth->execute;
    my $col = 0;
    my $string = "<h3>Categories</h3>";
    my $h;
    while($h = $sth->fetchrow_hashref) {    
    	$categories->{$h->{cat_id}} = $h->{cat_name};
    	$cat_descs->{$h->{cat_id}} = $h->{cat_desc};
    	$string .= "<li>[ ";
    	$string .= sprintf( "<a href=\"#X%d\">%s</a> ]", 
			    $h->{cat_id}, escapeHTML( $h->{cat_name} ) );
    	
    	#$string .= "  <tr>\n    " if($col == 0);
    	#$string .= sprintf("<td><A HREF=\"#X%d\">[%s]</A></td>\n", 
    	#		   $h->{cat_id}, escapeHTML($h->{cat_name}));
    	
    	if ( ++$col == 6 ) {
    	    $string .= "<br />";
    	    $col = 0;
    	}
    	
    	$string .= "</li>\n";    	
    }
    
    $sth->finish;
    
    #if($col != 0) {
	#while(++$col < 6) {
	#    $string .= "<td></td>";
	#}
	#$string .= "\n  </tr>\n";
    #}

    my $scsth = prepare("SELECT s.cat_id,  s.sc_id, s.sc_name  ".
			"FROM category AS c, sub_cat AS s " .
			"WHERE c.cat_id = s.cat_id ".
			"ORDER BY c.cat_name, s.sc_name", $dbh);
    my $ord = 0;
    $scsth->execute;

    while($h = $scsth->fetchrow_hashref) {
	my $id = 100000 * $h->{cat_id} + $h->{sc_id};
	$sc_descs->{$id} = {name => $h->{sc_name},
				 sort_ord => $ord++};
    }
    $scsth->finish;
    #dump_stuff("get_cats", "", "", $sc_descs);
    return $string;
}

# create an input object for selecting orders
# call with current order no, target order number
# returns a string ready for insertion and a hash of
# ord_nos =< names where current order name is 'Current'
sub order_selector {
    
    my ($ord_no, $this_order, $dbh) = @_;
    my  %labels;
    my $res = '<select name="order_no" id="order_no">' . "\n";
    
    my $sth = prepare("SELECT DISTINCT ord_no, ord_label FROM wh_order ".
			  "ORDER BY ord_no DESC", $dbh);
    $sth->execute;
    
    while ( my $h = $sth->fetchrow_hashref ) {
	
	$h->{ord_label} = "Current" if ( $h->{ord_no} == $ord_no );
	$labels{$h->{ord_no}} = escapeHTML( $h->{ord_label} );
	
	if ( $h->{ord_no} == $this_order ) {
	    
	    $res.= "<option selected value=\"$h->{ord_no}\">$labels{$h->{ord_no}}</option>\n";
	    
	} else {
	    
	    $res.= "<option value=\"$h->{ord_no}\">$labels{$h->{ord_no}}</option>\n";
	    
	}
	
    }
    
    $sth->finish;
    $res .= "</select>\n";
    $res .= '<noscript><input type="submit" name="go" value="go" /></noscript>';
    return (\%labels, $res);
    
}

# return a hash of member no to member name
sub mem_names_hash {
    my ($dbh) = @_;
    my %mem_names;

    my $sth = prepare("select * from mem_names_current_order", $dbh);
    $sth->execute;
    my $h;
    while($h = $sth->fetchrow_hashref) {
	my $name = $h->{mem_name};
	$name =~ s/ /&nbsp;/g;
	$mem_names{$h->{mem_id}} = $name;
    }
    $sth->finish;
    return \%mem_names;
}


# generate a drop down list of categories where the preselected output 
# is the current category. Passed product id, current category 
# returns a string creating a drop down menu. The <select name=xx> 
# part is not part of the string (allows putting it in the template

sub make_dropdown {
    my ($pr_cat, $categories) = @_;

    my $s = "";
    foreach my $c (sort 
		   {$categories->{$a} cmp $categories->{$b}} 
		   (keys(%{$categories}))) {
	$s  .= ($c eq $pr_cat) ? "<option selected" :
	    "<option";
	$s .= " value=\"$c\">$categories->{$c}</option>"
    }
    return $s;
}

# generate a drop down list of sub-categories where the preselected output 
# is the current sub-category. Passed product id, current category,
# current sub_category 
# returns a string creating a drop down menu. The <select name=xx> 
# part is not part of the string (allows putting it in the template

sub make_scdrop {
    my ($pr_cat, $pr_sc, $sc_descs) = @_;

    my $s = "";
    my %scs;
    foreach my $id (keys %{$sc_descs}) {
	next if(int($id /100000) != $pr_cat);
	$scs{$id % 100000} = $sc_descs->{$id}->{name};
    }
    #dump_stuff("make_scdrop", "sc_descs", "", $sc_descs);  
    #dump_stuff("make_scdrop", "scs", "", \%scs);  

    foreach my $sc (sort {$scs{$a} cmp $scs{$b}} (keys(%scs))) {
	$s  .= ($sc eq $pr_sc) ? "<option selected" :
	    "<option";
	$s .= " value=\"$sc\">$scs{$sc}</option>"
    }
    #dump_stuff("make_scdrop", "", "", {pr_cat =>$pr_cat, pr_sc=>$pr_sc, $s});  
    return $s;
}

# email generation routines
# open an email, return a file handle for printing output
sub email_header {
    my ($to, $subject, $config) = @_;
    my $tpl = new CGI::FastTemplate($config->{mailtmpls});
    my $now = scalar(localtime(time)),

    $tpl->strict();
    $tpl->define(header => "mail_header.template");
    my $h = {admin_email => $config->{admin_email},
	     email       => $to,
	     subject     => $subject,
	     now         => $now
    };
    $tpl->assign($h);
    $tpl->parse(MAIN => "header");
    my $ref = $tpl->fetch("MAIN");
    my $fh;
    open($fh, "| $config->{mailer}") or die
	"Can't open mail program: $config->{mailer}: $!";
    print $fh $$ref;
    return($fh);
}

# print a block of text to an email, using a template
# and a value hash
sub email_chunk {
    my ($fh, $template, $hash, $config) = @_;

    my $tpl = new CGI::FastTemplate($config->{mailtmpls});
    $tpl->strict();
    $tpl->define(header => $template);
    $tpl->assign($hash);
    $tpl->parse(MAIN => "header");
    my $ref = $tpl->fetch("MAIN");
    print $fh $$ref;
}

# print a series of rows to an email
# input is an array of hash refs, 
# the array will be unpacked in order and 
# each hash applied to the template

sub email_rows {
    my ($fh, $template, $hasharr, $config) = @_;
    foreach my $h (@{$hasharr}) {
	my $tpl = new CGI::FastTemplate($config->{mailtmpls});
	$tpl->strict();
	$tpl->define(header => $template);
	$tpl->assign($h);
	$tpl->parse(MAIN => "header");
	my $ref = $tpl->fetch("MAIN");
	print $fh $$ref;
    }
}

# get the order totals as an array
# returns ref to array with
# 3 sets of 3 values - total-items-at-rate, btw-at-rate,rate
# then total-ex-btw, total-btw, order-total (including payments

sub get_ord_totals {
    my ($mem, $ord, $dbh) = @_;
    my $sth = prepare("SELECT order_totals(?, ?)", $dbh);
    $sth->execute($mem, $ord);
    my $str = $sth->fetchrow_arrayref()->[0];
    # remove the wrapper parens
    $str =~ s/^.(.*)./$1/;
    my @arr = split(/,/, $str);
    return \@arr;
}

# debugging dump of some information
sub dump_stuff {
    my ($where, $what, $str, $ref) = @_;
    open(FRED, ">> /tmp/fred");
    chmod 0666, "/tmp/FRED";
    print FRED "$where begin $what\n";
    print FRED "$str\n" if(defined($str));
    print FRED Dumper($ref) if(defined($ref));
    print FRED "$where end $what\n";
    close(FRED);
}

END { }       # module clean-up code here (global destructor)


1;
