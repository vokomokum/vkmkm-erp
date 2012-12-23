-- insert some needed data that the app does not generate by itself (in tests/base.py)

BEGIN TRANSACTION;
CREATE TABLE wh_order (
    ord_no INTEGER NOT NULL, 
    ord_label VARCHAR(255),
    who_order_completed DATE, 
    PRIMARY KEY (ord_no, ord_label)
);


INSERT INTO "wh_order" VALUES(1,'May 2012', '2012-05-28 17:35:23');
INSERT INTO "wh_order" VALUES(2,'June 2012', '2012-06-27 17:35:23');
INSERT INTO "wh_order" VALUES(3,'July 2012', '2012-07-29 17:35:23');
INSERT INTO "wh_order" VALUES(4,'August 2012', '2012-08-30 17:35:23');
INSERT INTO "wh_order" VALUES(5,'September 2012', '2012-09-29 17:35:23');

--CREATE TABLE order_header (ord_no integer NOT NULL, ord_label character varying NOT NULL);
--INSERT INTO "order_header" VALUES(1,'current_order');

CREATE TABLE wholesaler (
	wh_id INTEGER PRIMARY KEY, 
	wh_name VARCHAR(100), 
	wh_addr1 VARCHAR(50), 
	wh_addr2 VARCHAR(50), 
	wh_addr3 VARCHAR(50), 
	wh_city VARCHAR(50), 
	wh_postcode VARCHAR(10), 
	wh_tel VARCHAR(20), 
	wh_fax VARCHAR(20), 
        wh_active boolean DEFAULT true,
	wh_update VARCHAR(20)
);

INSERT INTO "wholesaler" VALUES(1,'DNB', '', '', '', 'Amsterdam', '', '', '', true, '2012-11-29 17:35:23');
INSERT INTO "wholesaler" VALUES(2,'Zapatista', '', '', '', 'Hamburg', '', '', '', true, '2012-11-29 17:35:23');
INSERT INTO "wholesaler" VALUES(3,'De Werkbij', '', '', '', 'Amsterdam', '', '', '', true, '2012-11-29 17:35:23');

INSERT INTO "vers_suppliers" VALUES(1,'Geijtenboerderij', '', '', '', '', '', true);
INSERT INTO "vers_suppliers" VALUES(2,'Boerderij B', '', '', '', '', '', true);

COMMIT;
