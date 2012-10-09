-- insert some needed data that the member app does not generate by itself

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
COMMIT;
