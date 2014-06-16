from datetime import datetime
import sys
from members.models.mutation import Mutation
from members.models.base import DBSession
import csv

__author__ = 'diederick'


# 0:Boekdatum,1:Rekeningnummer,2:Bedrag,3:Debet / Credit,
# 4:Naam tegenrekening,5:Tegenrekening,6:Code,7:Omschrijving

# 05-04-2014,NL49TRIO0786829109,"160,54",Credit,
# F.O. Hamer,TRIONL2U NL56TRIO0784768412,ET,"F.Hamer, lidmaatschapsnr.208"

#transfer_account:          NL49TRIO0786829109
#transfer_contra_account:   F.O. Hamer
#transfer_amount:           "160
#transfer_type:             54"
#transfer_name:Credit
#transfer_code:TRIONL2U NL56TRIO0784768412
#transfer_desc:ET
#transfer_date: None

def process_upload(upload, session):
    print 'process_upload()'
    now = datetime.now()
    file = str(upload.file)
    with open(file, 'rb') as f:
        reader = csv.reader(f, delimiter = ',', quoting = csv.QUOTE_MINIMAL)
        rownum = 0
        try:
            for row in reader:
                print 'row:'+str(row)
                if "Boekdatum" in row:
                    continue
                f = []
                for column in row:
                    print 'column:'+str(column)
                    f.append(column)


    # f = open(upload.file)
    # for line in f.readlines():
    #     f = line.split(',')
                print 'f.length:'+str(len(f))
                if len(f) > 7 and rownum > 0:

                    print 'transfer_account:'+          str(f[1])
                    print 'transfer_contra_account:'+   str(f[5])
                    print 'transfer_amount:'+           str(f[2])
                    print 'transfer_type:'+             str(f[3])
                    print 'transfer_name:'+             str(f[4])
                    print 'transfer_code:'+             str(f[6])
                    print 'transfer_desc:'+             str(f[7])
                    print 'transfer_date:'+             str(datetime.strptime(f[0], '%d-%m-%Y'))

                    mutation = Mutation(
                        upload_id               = upload.id,
                        created                 = upload.created,
                        processed               = now,
                        transfer_date           = now, #datetime.strptime(f[0], '%d-%m-%Y'), #('Jun 1 2005  1:33PM', '%b %d %Y %I:%M%p')
                        transfer_account        = f[1],
                        transfer_contra_account = f[5],
                        transfer_amount         = float(f[2].replace('"','', 2).replace(',','.')),
                        transfer_type           = f[3].lower(),
                        transfer_name           = f[4],
                        transfer_code           = f[6],
                        transfer_desc           = f[7]
                    )
                    print 'transfer_date: '+str(mutation.transfer_date)
                    #session = DBSession()
                    session.add(mutation)
                    session.flush()
                rownum += 1
        except csv.Error as e:
            print 'OOPS!'
            sys.exit('file %s, line %d: %s' % (upload.file, reader.line_num, e))

    # f.close()