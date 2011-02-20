#!/usr/bin/perl

use strict;
use POSIX qw( strftime );

my $tgt = strftime("/var/tmp/site-backups/vokotest.%a.tbz", localtime(time));

system("/bin/tar -cjf $tgt /var/www/vokotest");

my $tgt = strftime("/var/tmp/site-backups/voko.%a.tbz", localtime(time));
system("/bin/tar -cjf $tgt /var/www/voko");


exit 0;
