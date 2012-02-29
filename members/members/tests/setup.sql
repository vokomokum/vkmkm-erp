-- insert some needed data that the member app does not generate by itself

BEGIN TRANSACTION;
CREATE TABLE wh_order (
    ord_no INTEGER NOT NULL, 
    ord_label VARCHAR(255), 
    PRIMARY KEY (ord_no)
);

INSERT INTO "wh_order" VALUES(1,'Order No. 1');
INSERT INTO "wh_order" VALUES(2,'Order No. 2');
INSERT INTO "wh_order" VALUES(3,'Order No. 3');
INSERT INTO "wh_order" VALUES(4,'Order No. 4');
INSERT INTO "wh_order" VALUES(5,'Order No. 5');

CREATE TABLE order_header (ord_no integer NOT NULL, ord_label character varying NOT NULL);
INSERT INTO "order_header" VALUES(1,'current_order');
COMMIT;
