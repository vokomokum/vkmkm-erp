#!/usr/bin/perl

use strict;
use POSIX qw( strftime );

my $tgt = strftime("/var/tmp/dbbackups/vokotest.%a.%H", localtime(time));

system("/usr/bin/pg_dump", "vokotest", "-f", $tgt);


my $tgt = strftime("/var/tmp/dbbackups/voko.%a.%H", localtime(time));
system("/usr/bin/pg_dump", "voko", "-f", $tgt);

exit 0;
