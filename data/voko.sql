--
-- PostgreSQL database dump
--

SET client_encoding = 'SQL_ASCII';
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON SCHEMA public IS 'Standard public schema';


--
-- Name: plperl; Type: PROCEDURAL LANGUAGE; Schema: -; Owner: 
--

CREATE PROCEDURAL LANGUAGE plperl;


--
-- Name: plpgsql; Type: PROCEDURAL LANGUAGE; Schema: -; Owner: 
--

CREATE PROCEDURAL LANGUAGE plpgsql;


SET search_path = public, pg_catalog;

--
-- Name: order_sums; Type: TYPE; Schema: public; Owner: jes
--

CREATE TYPE order_sums AS (
	btw_0_prods integer,
	btw_0_tax integer,
	btw_0_rate numeric,
	btw_1_prods integer,
	btw_1_tax integer,
	btw_1_rate numeric,
	btw_2_prods integer,
	btw_2_tax integer,
	btw_2_rate numeric,
	prod_tot integer,
	tax_tot integer,
	grand_tot integer
);


ALTER TYPE public.order_sums OWNER TO jes;

--
-- Name: add_order_to_member(integer, integer, integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION add_order_to_member(integer, integer, integer, integer) RETURNS void
    AS $_$
  DECLARE
    pr_no  	 ALIAS FOR $1;
    new_qty	 ALIAS FOR $2;
    m_no	 ALIAS FOR $3;
    md		 ALIAS FOR $4;
    mode	 INTEGER;  
    wmem_qty	 INTEGER;
    max_adj	 INTEGER;
    w_qty	 INTEGER;
    w_rcv	 INTEGER;
    mem_no	 INTEGER;
    order_no	 INTEGER;
    wh_no	 INTEGER;
    status	 INTEGER;
    cnt	 	 INTEGER;
    new_over	 INTEGER;
    old_over	 INTEGER;
    special	 BOOLEAN := 0;
    old_qty	 INTEGER;             -- old member line item qty
    old_m_whq	 INTEGER;	      -- old member order wholesale units
    new_m_whq	 INTEGER;	      -- new member order wholesale units
    new_w_qty	 INTEGER;             -- new wholesaler qty
    delta_m_qty     INTEGER;	      -- change in member qty
    delta_w_qty     INTEGER;          -- change in wholesale qty 
    delta_w_rcv     INTEGER;          -- change in wholesale rcv qty
    delta_w_pr      INTEGER := 0;     -- change in wholesale price ex btw
    delta_w_pr_btw  NUMERIC := 0;     -- change in wholsale price w/btw
    mo_exc_flg	    BOOLEAN := False;
    mo_exc_msg	    VARCHAR := ' ';
    ml_must_exist   BOOLEAN := False;
    who_must_exist  BOOLEAN := False;
    whl_must_exist  BOOLEAN := False;
    pr_rec	 product%ROWTYPE;
    wh_rec	 wh_order%ROWTYPE;
    wl_rec	 wh_line%ROWTYPE;
    ml_rec	 mem_line%ROWTYPE;
    mo_rec	 mem_order%ROWTYPE;
  BEGIN
    mode := md;
    mem_no := m_no;
    order_no := get_ord_no();
    status := get_ord_status();
    SELECT INTO special mem_adm_adj FROM members 
      WHERE mem_id = mem_no AND mem_active;
    IF(NOT FOUND) THEN
      RAISE EXCEPTION 'Invalid member number';
    END IF;

--     IF (mode = 0 AND status = 2) THEN
--        SELECT INTO mo_rec * FROM mem_order 
--           WHERE ord_no = order_no AND mem_id = mem_no;
--        IF NOT FOUND THEN
--          RAISE EXCEPTION 'Only committed orders can be processed, you can not start an order now';
--        END IF;
--     END IF;

    IF(mode > 2 AND NOT special) THEN
      RAISE EXCEPTION 'Not a privileged account';
    ELSIF(mode > 2) THEN
       mode := mode - 3;
    END IF;
    -- members can only change things during status 0/1/2 times
    IF((NOT special AND mode = 0 AND status >= 3) OR 
       (mode = 0 AND status >= 4)) THEN
      RAISE EXCEPTION 'Order is committed and can not be changed';
    END IF;
    -- admins can only adjust down during 3 and 6
    IF(mode = 1 AND status != 3) THEN
      RAISE EXCEPTION 'Can not adjust shortages now';
    END IF;
    -- can only deal with deliveries during status 6
    IF(mode = 2 AND status != 6) THEN
      RAISE EXCEPTION 'Can not adjust for delivery shortages now';
    END IF;
    IF(status = 4 OR status = 5 OR status = 7) THEN
      RAISE EXCEPTION 'No changes can be made to orders now';
    END IF;
    -- get the product details
    SELECT INTO pr_rec * FROM product WHERE pr_id = pr_no AND pr_active;
    -- filter out quantities that don't meet the requirement for
    -- multiples (even the special account doesn't help here, since
    -- having a non-multiple special order requires a non-multiple
    -- other member order
    IF(((new_qty % pr_rec.pr_mem_q) != 0) AND (status < 5)) THEN
      RAISE EXCEPTION 'product % must be ordered in multiples of %', pr_no,
        pr_rec.pr_mem_q;
    END IF;

    wh_no = pr_rec.pr_wh;
    -- for mode 0, we want to ensure that the new qty does not make
    -- the shortage bigger than the old quantity (except for the
    -- special accout)
    -- for mode 1  we want a limit on how far we can reduce the
    -- member order quantity - it can only be reduced until it makes
    -- the wholesale order come out correctly, again excepting the 
    -- special account

    -- if wholesale orders are in units of 1, then all member amounts
    -- are always OK without adjusting
    IF(mode = 1 AND pr_rec.pr_wh_q = 1) THEN
      RAISE EXCEPTION 'This product can not require adjusting';
    END IF;

    IF((mode > 0) OR (mode = 0 AND status = 2)) THEN
      -- read the member line item to get current quantity
      SELECT INTO old_qty meml_pickup FROM mem_line WHERE
        ord_no = order_no AND pr_id = pr_no AND mem_id = mem_no;
      IF(NOT FOUND) THEN
        IF(mode > 0) THEN
          RAISE EXCEPTION 'Can not find member line item for product';
        ELSE
          old_qty = 0;
        END IF;
      END IF;
     
      -- read the wholesale line record and get the shortage. This 
      -- should not fail, because there should always be a wholesale
      -- line record if there is a member line record, but we check
      -- anyway (now amended to allow adding new product)
      SELECT INTO wmem_qty, w_qty,  w_rcv whl_mem_qty, whl_qty, whl_rcv
         FROM wh_line WHERE ord_no = order_no AND pr_id = pr_no;
      IF(NOT FOUND) THEN
        IF mode > 1 THEN
          RAISE EXCEPTION 'Can not add new products to wholesale order';
        ELSE
          wmem_qty := 0;
	  w_qty := 0;
	END IF;
      END IF;

      -- convert wholesale quantities to member quantities
      w_qty := w_qty * pr_rec.pr_wh_q;
      w_rcv := w_rcv * pr_rec.pr_wh_q;

      -- for ordering during member adjusting time, don't accept
      -- orders that make things worse
      IF(mode = 0 AND NOT special) THEN
        -- RAISE NOTICE 'wmem_qty % old_qty % new_qty % pr_wh_q % special %',
	--      		wmem_qty, old_qty, new_qty, pr_rec.pr_wh_q, special;
	new_over := (wmem_qty - old_qty + new_qty) % pr_rec.pr_wh_q;
	old_over := wmem_qty % pr_rec.pr_wh_q;
        IF((old_over = 0 AND new_over != 0) OR
	(new_over != 0 AND new_over < old_over)) THEN
          RAISE EXCEPTION 'This quantity increases the shortage';
	END IF;
      -- during order adjustmetns, don't allow taking too much off
      ELSIF(mode = 1 AND NOT special) THEN
        max_adj := wmem_qty - w_qty;
        IF(new_qty < old_qty - max_adj) THEN
          RAISE EXCEPTION 'This adjustment is too large for the shortage';
        END IF;
      -- mode 2, delivery shortages
      ELSIF mode = 2 THEN
        max_adj := wmem_qty - w_rcv;
        IF(new_qty < old_qty - max_adj) THEN
          RAISE EXCEPTION 'This adjustment is too large for the shortage';
        END IF;
      END IF;
    END IF;
    -- create a new, uncommitted order if none exists and we are a
    -- member and commits are not closed
    IF((mode = 0 AND status >= 3 AND NOT special) OR
       (mode = 0 AND status = 3 AND special)) THEN
        mo_exc_flg := True; 
        mo_exc_msg := 'Can not start new order now';
    ELSIF((mode = 3) OR (mode = 2 AND NOT special)) THEN
        mo_exc_flg := True;
	mo_exc_msg := 'Only member can create an order';
    END IF;

    mo_rec := open_mem_ord(mem_no, mo_exc_flg, mo_exc_msg);
    -- get a copy of the line item record, create if need be
    ml_must_exist := ((mode = 1 AND NOT special) OR (mode = 2));
    ml_rec := open_mem_line(order_no, mem_no, pr_rec, ml_must_exist, 
      'Can not add new lines to member orders during adjustments');
    -- get a copy of the wholesale record, create if need be and allowd)
    who_must_exist := ((mode = 1 AND NOT special) OR (MODE = 2));
    wh_rec := open_wh_ord(wh_no, who_must_exist, 
              'Can not create new wholesaler order now');
    whl_must_exist := (mode != 0);
    wl_rec := open_wh_line(order_no, wh_no, pr_rec, whl_must_exist,
      'Can not add new products to wholesale orders now');

    -- decide what quantity we are changing, update the others
    -- ie, member orders change ordered, adjusted and received
    -- admin adjustments change adjusted and received
    -- admin delivery shortages change only received
    IF(mode = 0) THEN                       -- member order
      old_qty         := ml_rec.meml_qty;  
      ml_rec.meml_qty := new_qty;           -- set adj and rcv to mem. qty.
      ml_rec.meml_adj := new_qty;
      ml_rec.meml_rcv := new_qty;
    ELSIF(mode = 1) THEN                    -- adjusting for shortages
      old_qty         := ml_rec.meml_adj;   -- old adjusted qty
      ml_rec.meml_adj := new_qty;           -- new qty to adj and rcv
      ml_rec.meml_rcv := new_qty;
    ELSE                                    -- delivery shortages
      old_qty         := ml_rec.meml_rcv;   -- old delivered qty
      ml_rec.meml_rcv := new_qty;           -- set new one
    END IF;
      ml_rec.meml_pickup := new_qty;
    delta_m_qty     := new_qty - old_qty; -- change in order qty
    -- you can''t back out on a committed order
    --IF(mode = 0 AND mo_rec.memo_commit_closed IS NOT NULL AND 
    --  (new_qty < old_qty) AND NOT special) THEN
    --  RAISE EXCEPTION 'The order is committed and quantities can not be reduced';
    -- END IF;
    old_m_whq := floor(old_qty/pr_rec.pr_wh_q);
    new_m_whq := floor(new_qty/pr_rec.pr_wh_q);

    -- admin's can''t increase customer order amounts
    IF(mode = 1 AND (new_qty > ml_rec.meml_qty) AND NOT special) THEN
      RAISE EXCEPTION 'Can''t increase member order';
    END IF;
    -- IF(mode = 2 AND (new_qty - old_qty > 0)) THEN
    --   RAISE EXCEPTION 'Can''t receive more than was ordered';
    -- END IF;
    -- when adjusting order shortages, we will never reduce a member
    -- order below a full wholesale quantity. This doesn't work with
    -- delivery shortages 
    IF(mode = 1 AND (new_m_whq < old_m_whq) AND NOT special) THEN
      RAISE EXCEPTION 'Can''t reduce member order below complete wholesale units';
    END IF;
    -- update member order header total price
    mo_rec.memo_amt := mo_rec.memo_amt + 
      pr_rec.pr_mem_price * delta_m_qty;

    -- uodate wholesale line item member quantity
    wl_rec.whl_mem_qty := wl_rec.whl_mem_qty + delta_m_qty;
    -- calculate change (if any) in wholesale line item order qty
    new_w_qty := floor(wl_rec.whl_mem_qty/pr_rec.pr_wh_q);
    delta_w_qty := new_w_qty - wl_rec.whl_qty;
      delta_w_pr := pr_rec.pr_wh_price * delta_w_qty;

      delta_w_pr_btw := pr_rec.pr_wh_price * delta_w_qty * 
        (100 + pr_rec.pr_btw);

    IF(mode < 2) THEN
      wl_rec.whl_qty := new_w_qty;
       -- calculate changes in wholesale price w/wo btw
      -- set wholesale order totals
      wh_rec.who_amt_ex_btw := wh_rec.who_amt_ex_btw + delta_w_pr;
      wh_rec.who_amt_btw := wh_rec.who_amt_btw + delta_w_pr_btw;
    END IF;
    IF(mode < 2) THEN
      -- not yet delivered, assume it will be
      wl_rec.whl_rcv := wl_rec.whl_qty;
    END IF;
    -- update the line items (member and wholesale) and the
    -- totals in the headers (member and wholesale) 
    -- don't write empty line items out, delete them instead
    -- delete only during ordinary member order times, keep to allow
    -- rollbacks otherwise
    IF((status < 2) AND (ml_rec.meml_qty = 0) AND (ml_rec.meml_adj = 0) AND 
       (ml_rec.meml_rcv = 0)) THEN
      DELETE FROM mem_line WHERE ord_no = order_no AND mem_id = mem_no 
       AND pr_id = pr_no;
    ELSE
      UPDATE mem_line SET meml_qty = ml_rec.meml_qty, 
        meml_adj = ml_rec.meml_adj, meml_rcv = ml_rec.meml_rcv,
        meml_pickup = ml_rec.meml_pickup
        WHERE ord_no = order_no AND mem_id = mem_no AND pr_id = pr_no;
    END IF;
    UPDATE mem_order SET memo_amt = mo_rec.memo_amt
      WHERE ord_no = order_no AND mem_id = mem_no;
    -- delete empty wholesale order lines during ordinary member order periods
    IF((wl_rec.whl_qty = 0) AND (wl_rec.whl_rcv = 0) AND
    (wl_rec.whl_mem_qty = 0) AND (status < 2))
      THEN
      DELETE FROM wh_line 
        WHERE ord_no = order_no AND wh_id = wh_no AND pr_id = pr_no;
    ELSE
      UPDATE wh_line SET whl_qty = wl_rec.whl_qty, whl_rcv = wl_rec.whl_rcv,
        whl_mem_qty = wl_rec.whl_mem_qty 
        WHERE ord_no = order_no AND wh_id = wh_no AND pr_id = pr_no;
    END IF;
    UPDATE wh_order SET who_amt_ex_btw = wh_rec.who_amt_ex_btw,
      who_amt_btw = wh_rec.who_amt_btw
      WHERE ord_no = order_no AND wh_id = wh_no;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.add_order_to_member(integer, integer, integer, integer) OWNER TO jes;

--
-- Name: broken_missing(integer, integer, integer, integer, boolean); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION broken_missing(mem_num integer, ord_num integer, pr_num integer, qty integer, is_damaged boolean) RETURNS void
    AS $$
  DECLARE
     order_no       INTEGER;
     status   	    INTEGER;
     m		    mem_line%ROWTYPE;
     is_checked_out BOOLEAN;
     delta          INTEGER;
     old_q          INTEGER;
  BEGIN
     order_no := get_ord_no();
     status   := get_ord_status();
     -- requires a valid order for member
     IF ord_num > order_no THEN
        RAISE EXCEPTION 'Invalid order number %', ord_no;
     END IF;
     -- current order only allows this at phase 7 (ready for pickup)
     IF order_no = ord_num AND status < 7 THEN
        RAISE EXCEPTION 'This order is not at the pickup stage';
     END IF;
     -- get the line item for member
     SELECT * INTO m FROM mem_line WHERE mem_id = mem_num AND
        ord_no = ord_num AND pr_id = pr_num;
     IF NOT FOUND THEN
        RAISE EXCEPTION 'Can''t find order for product % by  member %',
          pr_num,  mem_num;
     END IF;
     -- see if this order has alrady completed checking out
     SELECT mo_checked_out INTO is_checked_out FROM mem_order WHERE 
         mem_id = mem_num AND ord_no = ord_num;
     IF NOT FOUND THEN
        -- should never happen
        RAISE EXCEPTION 'Can''t find order header for member % order %',
          mem_num, ord_num;
     END IF;
     IF is_checked_out THEN
        RAISE EXCEPTION 'This order is already checked out';
     END IF;
     -- see if this changes anything 
     old_q := m.meml_missing;
     IF is_damaged THEN
        old_q := m.meml_damaged;
     END IF;
     delta := old_q - qty;   
     -- bail out on no-change
     IF delta = 0 THEN RETURN; END IF;
     m.meml_pickup := m.meml_pickup + delta;
     -- don't get carried awau
     IF m.meml_pickup < 0 THEN
        RAISE EXCEPTION 'Damaged/Missing quantity is more than pickup qty';
     END IF;
     IF is_damaged THEN 
        m.meml_damaged := qty;
     ELSE
       m.meml_missing := qty;
     END IF;
     UPDATE mem_line SET meml_pickup = m.meml_pickup, meml_missing =
         m.meml_missing, meml_damaged = m.meml_damaged WHERE 
         mem_id = mem_num AND ord_no = ord_num AND pr_id = pr_num;
     RETURN;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.broken_missing(mem_num integer, ord_num integer, pr_num integer, qty integer, is_damaged boolean) OWNER TO jes;

--
-- Name: btw_price(integer, numeric); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION btw_price(ex_btw integer, btw numeric) RETURNS integer
    AS $$
    DECLARE
      int_btw  INTEGER;
    BEGIN
      int_btw = floor(10 * btw);

      RETURN (ex_btw * (1000 + int_btw) + 500) / 1000;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.btw_price(ex_btw integer, btw numeric) OWNER TO jes;

--
-- Name: check_mem_ord_allowed(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_mem_ord_allowed() RETURNS boolean
    AS $$
  DECLARE   
    status	INTEGER;
  BEGIN
    RETURN (get_ord_status() < 2);
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_mem_ord_allowed() OWNER TO jes;

--
-- Name: check_mem_ord_open(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_mem_ord_open(integer) RETURNS boolean
    AS $_$
  DECLARE   
    mem_no ALIAS FOR $1; 
    cnt INTEGER;
    order_no INTEGER; 
  BEGIN
    order_no := get_ord_no();
    SELECT INTO cnt count(*) FROM mem_order WHERE mem_id = mem_no 
      AND ord_no  = order_no;
    RETURN (cnt > 0);
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_mem_ord_open(integer) OWNER TO jes;

--
-- Name: check_prd_in_wh_line(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_prd_in_wh_line(integer) RETURNS boolean
    AS $_$
  DECLARE
    pid		ALIAS FOR $1;
    wh_no	INTEGER;
    wh_num	INTEGER;
    order_no	INTEGER;
    cnt		INTEGER;
    curs	CURSOR (ORDN INTEGER, PID INTEGER) FOR SELECT wh_id 
                  FROM wh_order WHERE pr_id = PID AND ord_no = ORDN;
   BEGIN
     order_no := get_ord_no();
     PERFORM wh_id FROM wh_line WHERE ord_no = order_no AND pr_id = pid;
     IF(NOT FOUND) THEN RETURN False; END IF;
     RETURN TRUE;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_prd_in_wh_line(integer) OWNER TO jes;

--
-- Name: check_unique_adm_adj(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_unique_adm_adj() RETURNS "trigger"
    AS $$
  DECLARE
    cnt INTEGER;
  BEGIN
    IF(NOT NEW.mem_adm_adj) THEN RETURN NULL; END IF;
    -- clear flags everywhere if more than one set
    SELECT INTO cnt count(*) FROM members WHERE mem_adm_adj;
    IF(cnt > 1)THEN
      UPDATE members SET mem_adm_adj = False
        WHERE mem_adm_adj;
    END IF;
    RETURN NULL;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_unique_adm_adj() OWNER TO jes;

--
-- Name: check_wh_ord_allowed(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_wh_ord_allowed() RETURNS boolean
    AS $$
  DECLARE   
    status	INTEGER;
  BEGIN
    RETURN (get_ord_status() < 7);
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_wh_ord_allowed() OWNER TO jes;

--
-- Name: check_wh_ord_open(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION check_wh_ord_open(integer) RETURNS boolean
    AS $_$
  DECLARE   
    wh_no ALIAS FOR $1; 
    cnt INTEGER;
  BEGIN
    SELECT INTO cnt count(*) FROM wh_order WHERE wh_id = wh_no 
      AND ord_no  = get_ord_no();
    RETURN (cnt > 0);
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.check_wh_ord_open(integer) OWNER TO jes;

--
-- Name: commit_order(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION commit_order(integer) RETURNS void
    AS $_$
  DECLARE
    mem_no	ALIAS FOR $1;
    order_no	INTEGER;
    status	INTEGER;
    mo_rec	mem_order%ROWTYPE;
  BEGIN
    order_no := get_ord_no();
    status := get_ord_status();
    IF(status = 0) THEN
      RAISE EXCEPTION 'Orders can not be committed yet';
    ELSIF(status > 2) THEN
      RAISE EXCEPTION 'It is too late to commit orders';
    END IF;
--     SELECT INTO mo_rec * FROM mem_order WHERE ord_no = order_no AND
--       mem_id = mem_no;
--     IF(NOT FOUND) THEN
--       RAISE EXCEPTION 'No order to commit for member %', mem_no;
--     END IF;
    PERFORM open_mem_ord(mem_no, False, '');
    UPDATE mem_order SET memo_commit_closed = LOCALTIMESTAMP 
      WHERE ord_no = order_no AND mem_id = mem_no;
    -- delete any old carry-overs
    DELETE FROM carry_over WHERE mem_id = mem_no;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.commit_order(integer) OWNER TO jes;

--
-- Name: count_all_rcv_shortages(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION count_all_rcv_shortages() RETURNS integer
    AS $$
  DECLARE
  order_no	INTEGER;
  cnt		INTEGER := 0;
  pr_no		INTEGER;
  m_rcv		INTEGER;
  w_m_rcv	INTEGER;
  ml_curs	CURSOR (ORDN INTEGER) FOR SELECT pr_id, sum(meml_rcv) 
  		  FROM mem_line WHERE ord_no = ORDN GROUP BY pr_id;
  BEGIN
    order_no := get_ord_no();
    open ml_curs(order_no);
    LOOP
      FETCH ml_curs INTO pr_no, m_rcv;
      EXIT WHEN NOT FOUND;
      SELECT INTO w_m_rcv p.pr_wh_q * l.whl_rcv 
        FROM wh_line AS l, product AS p
        WHERE l.ord_no = order_no AND l.pr_id = p.pr_id AND p.pr_active 
              AND p.pr_id = pr_no;
      IF(w_m_rcv < m_rcv) THEN cnt := cnt + 1; END IF;
    END LOOP;
    CLOSE ml_curs;
    RETURN cnt;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.count_all_rcv_shortages() OWNER TO jes;

--
-- Name: count_all_shortages(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION count_all_shortages() RETURNS integer
    AS $$
  DECLARE
  order_no	INTEGER;
  cnt		INTEGER := 0;
  pr_no		INTEGER;
  m_adj		INTEGER;
  w_m_adj	INTEGER;
  ml_curs	CURSOR (ORDN INTEGER) FOR SELECT pr_id, sum(meml_adj) 
  		  FROM mem_line WHERE ord_no = ORDN GROUP BY pr_id;
  BEGIN
    order_no := get_ord_no();
    open ml_curs(order_no);
    LOOP
      FETCH ml_curs INTO pr_no, m_adj;
      EXIT WHEN NOT FOUND;
      SELECT INTO w_m_adj p.pr_wh_q * l.whl_qty 
        FROM wh_line AS l, product AS p
        WHERE l.ord_no = order_no AND l.pr_id = p.pr_id AND p.pr_active 
	AND p.pr_id = pr_no;
      IF(w_m_adj < m_adj) THEN cnt := cnt + 1; END IF;
    END LOOP;
    CLOSE ml_curs;
    RETURN cnt;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.count_all_shortages() OWNER TO jes;

--
-- Name: count_wh_ord_shortages(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION count_wh_ord_shortages(integer) RETURNS integer
    AS $_$
  DECLARE
  wh_no		ALIAS FOR $1;
  order_no	INTEGER;
  cnt		INTEGER := 0;
  BEGIN
    order_no := get_ord_no();
    PERFORM * FROM wholesaler WHERE wh_id = wh_no AND wh_active;
    IF(NOT FOUND) THEN RETURN 0; END IF;
    SELECT INTO cnt count(*) FROM wh_line AS l, product AS p
      WHERE l.wh_id = wh_no AND l.ord_no = order_no AND l.pr_id = p.pr_id AND
      l.whl_qty != floor(p.pr_wh_q/l.whl_mem_qty);
    RETURN cnt;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.count_wh_ord_shortages(integer) OWNER TO jes;

--
-- Name: create_carry_over(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION create_carry_over(integer) RETURNS void
    AS $_$
  DECLARE
    mem_no      ALIAS FOR $1;
    order_no	INTEGER;
    pr_no	INTEGER;
    quantity	INTEGER;
    litems	CURSOR (MEM INTEGER, ORDN INTEGER) FOR 
    		  SELECT pr_id, meml_qty FROM mem_line
		  WHERE mem_id = MEM AND ORDN = ORDN;
  BEGIN
    order_no := get_ord_no();
    -- get rid of old carry over
    DELETE FROM carry_over WHERE mem_id = mem_no;
    -- and leave it deleted if there is a default
    PERFORM pr_id FROM default_order where mem_id = mem_no;
    IF(FOUND) THEN RETURN; END IF;

    open litems(mem_no, order_no);
    LOOP
      FETCH litems INTO pr_no, quantity;
      EXIT WHEN NOT FOUND;
      IF quantity = 0 THEN CONTINUE; END IF;
      PERFORM qty FROM carry_over WHERE mem_id = mem_no AND
        pr_id = pr_no;
      IF FOUND THEN
         UPDATE carry_over SET qty = quantity WHERE mem_id = mem_no
           AND pr_id = pr_no;
      ELSE
        RAISE NOTICE 'mem_no: %s, pr_no: %s, qty: %s', mem_no, pr_no, quantity;
        INSERT INTO carry_over (mem_id, pr_id, qty) 
        VALUES (mem_no, pr_no, quantity);
      END IF;
    END LOOP;
    CLOSE litems;
    DELETE FROM mem_line  WHERE mem_id = mem_no AND ord_no = order_no;
    DELETE FROM mem_order WHERE mem_id = mem_no AND ord_no = order_no;
    -- raise notice 'Done';

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.create_carry_over(integer) OWNER TO jes;

--
-- Name: create_default_order(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION create_default_order(integer) RETURNS void
    AS $_$
  DECLARE
    mem_no      ALIAS FOR $1;
    order_no	INTEGER;
    pr_no	INTEGER;
    quantity	INTEGER;
    commit_ts	TIMESTAMP;
    litems	CURSOR (MEM INTEGER, ORDN INTEGER) FOR 
    		  SELECT pr_id, meml_qty FROM mem_line
		  WHERE mem_id = MEM AND ord_no = ORDN;
  BEGIN
    order_no = get_ord_no();
    SELECT memo_commit_closed INTO commit_ts FROM mem_order 
        WHERE mem_id = mem_no AND ord_no = order_no;

    -- if they've no order, bail out, existing default remains
    IF(NOT FOUND) THEN RETURN; END IF;

    -- they've ordered something, blow away the old default
    DELETE FROM default_order WHERE mem_id = mem_no;
    -- and any carry-over    
    DELETE FROM carry_over WHERE mem_id = mem_no;
    open litems(mem_no, order_no);
    LOOP
      FETCH litems INTO pr_no, quantity;
      EXIT WHEN NOT FOUND;
      RAISE LOG 'create_default_order mem_id: %, pr_id: %, qty: %',
            mem_no, pr_no, quantity;
      INSERT INTO default_order (mem_id, pr_id, qty) 
        VALUES (mem_no, pr_no, quantity);
    END LOOP;
    CLOSE litems;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.create_default_order(integer) OWNER TO jes;

--
-- Name: create_default_order(integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION create_default_order(integer, integer) RETURNS void
    AS $_$
  DECLARE
    mem_no      ALIAS FOR $1;
    order_no	ALIAS FOR $2;
    pr_no	INTEGER;
    quantity	INTEGER;
    commit_ts	TIMESTAMP;
    litems	CURSOR (MEM INTEGER, ORDN INTEGER) FOR 
    		  SELECT pr_id, meml_qty FROM mem_line
		  WHERE mem_id = MEM AND ord_no = ORDN;
  BEGIN
    -- pick an arbitrary field to check that there is such an order
    SELECT memo_commit_closed INTO commit_ts FROM mem_order 
        WHERE mem_id = mem_no AND ord_no = order_no;

    -- if they've no order, bail out, existing default remains
    IF(NOT FOUND) THEN RETURN; END IF;

    -- they've ordered something, blow away the old default
    DELETE FROM default_order WHERE mem_id = mem_no;
    -- and any carry-over    
    DELETE FROM carry_over WHERE mem_id = mem_no;
    open litems(mem_no, order_no);
    LOOP
      FETCH litems INTO pr_no, quantity;
      EXIT WHEN NOT FOUND;
      RAISE LOG 'create_default_order mem_id: %, pr_id: %, qty: %',
            mem_no, pr_no, quantity;
      INSERT INTO default_order (mem_id, pr_id, qty) 
        VALUES (mem_no, pr_no, quantity);
    END LOOP;
    CLOSE litems;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.create_default_order(integer, integer) OWNER TO jes;

--
-- Name: dnb_interval(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION dnb_interval(OUT newest timestamp with time zone, OUT penult timestamp with time zone) RETURNS record
    AS $$
   DECLARE
     dnbtime CURSOR FOR 
                SELECT DISTINCT wh_last_seen 
                FROM dnbdata ORDER BY wh_last_seen DESC LIMIT 2;
   BEGIN
     OPEN dnbtime;
     FETCH dnbtime INTO newest;
     FETCH dnbtime INTO penult;
     CLOSE dnbtime;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.dnb_interval(OUT newest timestamp with time zone, OUT penult timestamp with time zone) OWNER TO jes;

--
-- Name: drop_mem_empty_orders(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION drop_mem_empty_orders(integer) RETURNS void
    AS $_$
  DECLARE 
    order_no    ALIAS FOR $1; 
    mem_no    	INTEGER;
    cnt		INTEGER;
  BEGIN
    -- get rid of the empty line items
    DELETE FROM mem_line WHERE ord_no = order_no AND meml_rcv = 0 
      AND meml_adj = 0 AND meml_qty = 0 AND meml_pickup = 0;
    DELETE FROM mem_order WHERE ord_no = order_no and mem_id NOT IN
      (SELECT DISTINCT mem_id FROM mem_line as l  WHERE l.ord_no = order_no
        AND (l.meml_adj != 0 OR l.meml_rcv != 0));
    PERFORM rebuild_all_wh_headers();

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.drop_mem_empty_orders(integer) OWNER TO jes;

--
-- Name: enter_delivery_shortage(integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION enter_delivery_shortage(integer, integer) RETURNS void
    AS $_$
  DECLARE
    pr_no	ALIAS FOR $1;
    qty		ALIAS FOR $2;
    order_no	INTEGER;
    status	INTEGER;
    delta_rcv	INTEGER;
    
    wh_rec	wh_order%ROWTYPE;
    wl_rec	wh_line%ROWTYPE;
  BEGIN
    order_no := get_ord_no();
    status   := get_ord_status();
    IF(status != 5) THEN
      RAISE EXCEPTION 'Can not enter delivery shortages now';
    END IF;

    SELECT INTO wl_rec * FROM wh_line WHERE ord_no = order_no AND
       pr_id = pr_no;
    IF(NOT FOUND) THEN
      RAISE EXCEPTION 'Can not find product % in order %',
        pr_no, order_no;
    END IF;

    SELECT INTO wh_rec * FROM wh_order WHERE ord_no = order_no AND 
      wh_id = wl_rec.wh_id;
    IF(NOT FOUND) THEN
      RAISE EXCEPTION 'Missing wh_order entry for wholesaler %, order %',
        wl_rec.wh_id, order_no;
    END IF;

    -- if quantity is unchanged, bail out now
    IF(qty = wl_rec.whl_rcv) THEN RETURN; END IF;
    IF(qty > wl_rec.whl_qty) THEN
      RAISE EXCEPTION 'Can not receive more than was ordered';
    END IF;

    delta_rcv = qty - wl_rec.whl_rcv;
    UPDATE wh_line SET whl_rcv = qty WHERE ord_no = order_no AND 
      pr_id = pr_no;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.enter_delivery_shortage(integer, integer) OWNER TO jes;

--
-- Name: ex_btw_prc(integer, numeric); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION ex_btw_prc(price integer, btw numeric) RETURNS integer
    AS $$
  DECLARE
    int_btw    INTEGER;
  BEGIN
    -- convert btw to integer
    int_btw := floor(10 * btw);
    -- creates the ex-btw price
    RETURN (price * 1000 + 500)/ (1000 + int_btw);
    
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.ex_btw_prc(price integer, btw numeric) OWNER TO jes;

--
-- Name: first_insert(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION first_insert() RETURNS "trigger"
    AS $$  -- TESTED
  DECLARE cnt		INTEGER;
  BEGIN
    SELECT INTO cnt count(*) FROM order_header;
    IF(cnt != 0) THEN 
      RAISE EXCEPTION 'Only one insert allowed for order_header';
      RETURN NEW;
    END IF;
    NEW.mas_key := 1;
    NEW.ord_no := 0;
    NEW.ord_status := 7;
    RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.first_insert() OWNER TO jes;

--
-- Name: fix_up(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION fix_up() RETURNS void
    AS $$
  DECLARE
    p	         record;
    pr           cursor for select pr_id, pr_mem_price, pr_ex_btw, pr_btw from product
            where pr_id in (select distinct pr_id from mem_line);
    BEGIN
    open pr;
    loop
      fetch pr into p;
      exit when not found;
      update mem_line set meml_unit_price = p.pr_mem_price, meml_ex_btw =
             p.pr_ex_btw, meml_btw = p.pr_btw where pr_id = p.pr_id;
     end loop;
     
     return;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.fix_up() OWNER TO jes;

--
-- Name: get_ord_no(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION get_ord_no() RETURNS integer
    AS $$
  DECLARE   ord_no	INTEGER;
  BEGIN
    SELECT INTO ord_no order_header.ord_no FROM order_header;
    RETURN (ord_no);
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.get_ord_no() OWNER TO jes;

--
-- Name: get_ord_status(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION get_ord_status() RETURNS integer
    AS $$
  DECLARE status INTEGER;
  BEGIN
    SELECT INTO status ord_status FROM order_header;
    RETURN status;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.get_ord_status() OWNER TO jes;

--
-- Name: join_name(character varying, character varying, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION join_name(character varying, character varying, character varying) RETURNS character varying
    AS $_$  -- NOT TESTED
  DECLARE 
   first	ALIAS FOR $1;
   middle	ALIAS FOR $2;
   last		ALIAS FOR $3;
  BEGIN
     IF middle = ''
        THEN
          RETURN  first || ' ' || last;
     END IF;

     RETURN first || ' ' || middle || ' ' || last;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.join_name(character varying, character varying, character varying) OWNER TO jes;

--
-- Name: message_update(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION message_update() RETURNS "trigger"
    AS $$
   BEGIN
      IF (NEW.mem_message = OLD.mem_message)
      THEN
         NEW.mem_message_auth = OLD.mem_message_auth;
         NEW.mem_message_date = OLD.mem_message_date;
      ELSE
         NEW.mem_message_date = LOCALTIMESTAMP;
      END IF;
      RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.message_update() OWNER TO jes;

--
-- Name: min_price(integer, numeric, integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION min_price(w_price integer, btw numeric, margin integer, w_q integer) RETURNS integer
    AS $$
  DECLARE
    ex_btw       INTEGER; 
  BEGIN
    -- caclulate an ex_btw recommended price (including the margin)
    ex_btw := ((w_price * (100 + margin) / w_q) + 99) /100;
    -- return that price with btw included
    RETURN  btw_price(ex_btw, btw);

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.min_price(w_price integer, btw numeric, margin integer, w_q integer) OWNER TO jes;

--
-- Name: news_insert(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION news_insert() RETURNS "trigger"
    AS $$
   BEGIN
      NEW.news_date     := LOCALTIMESTAMP;
      NEW.news_mod_auth := NEW.news_auth;
      NEW.news_mod_date := NEW.news_date;
      RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.news_insert() OWNER TO jes;

--
-- Name: news_update(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION news_update() RETURNS "trigger"
    AS $$
   BEGIN
      IF (NEW.news_text = OLD.news_text)
         THEN
            NEW.news_mod_auth := OLD.news_mod_auth;
            NEW.news_mod_date := OLD.news_mod_date;
         ELSE
            NEW.news_mod_date := LOCALTIMESTAMP;
      END IF;
      NEW.news_auth     := OLD.news_auth;
      NEW.news_date     := OLD.news_date;
      RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.news_update() OWNER TO jes;

--
-- Name: product_pr_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE product_pr_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.product_pr_id_seq OWNER TO jes;

SET default_tablespace = '';

SET default_with_oids = true;

--
-- Name: product; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE product (
    pr_id integer DEFAULT nextval('product_pr_id_seq'::regclass) NOT NULL,
    pr_cat integer NOT NULL,
    pr_sc integer NOT NULL,
    pr_wh integer,
    pr_wh_q integer NOT NULL,
    pr_margin integer DEFAULT 5,
    pr_mem_q integer NOT NULL,
    pr_wh_price integer NOT NULL,
    pr_mem_price integer,
    pr_desc character varying NOT NULL,
    wh_prcode character varying NOT NULL,
    wh_desc character varying NOT NULL,
    pr_active boolean DEFAULT true,
    pr_btw numeric NOT NULL,
    pr_changed boolean DEFAULT false,
    pr_mq_chg boolean DEFAULT false,
    pr_ex_btw integer,
    CONSTRAINT minimum_margin CHECK ((pr_margin >= 4)),
    CONSTRAINT not_null_pr_ex_btw CHECK ((pr_ex_btw IS NOT NULL)),
    CONSTRAINT positive_price CHECK ((pr_wh_price > 0)),
    CONSTRAINT valid_btw_rate CHECK ((((pr_btw = (0)::numeric) OR (pr_btw = (6)::numeric)) OR (pr_btw = (19)::numeric))),
    CONSTRAINT valid_multiple CHECK ((((pr_wh_q % pr_mem_q) = 0) OR ((pr_mem_q % pr_wh_q) = 0)))
);


ALTER TABLE public.product OWNER TO jes;

--
-- Name: open_mem_line(integer, integer, product, boolean, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION open_mem_line(order_no integer, mem_no integer, pr_rec product, exc_flg boolean, exc_msg character varying) RETURNS record
    AS $$
  DECLARE   
    status	  INTEGER;
    ml_rec	  mem_line%ROWTYPE;
  BEGIN
    status := get_ord_status();

    SELECT INTO ml_rec * FROM mem_line WHERE ord_no = order_no AND
      mem_id = mem_no AND pr_id = pr_rec.pr_id;

    IF(FOUND) THEN RETURN ml_rec; END IF;
    IF(exc_flg) THEN RAISE EXCEPTION 'open_mem_line: %', exc_msg; END IF;
    ml_rec.ord_no          := order_no; 
    ml_rec.mem_id          := mem_no;
    ml_rec.pr_id           := pr_rec.pr_id;
    ml_rec.meml_qty	   := 0;
    ml_rec.meml_adj	   := 0;
    ml_rec.meml_rcv        := 0;
    ml_rec.meml_pickup     := 0;
    ml_rec.meml_unit_price := pr_rec.pr_mem_price;
    ml_rec.meml_btw	   := pr_rec.pr_btw;
    ml_rec.meml_ex_btw     := pr_rec.pr_ex_btw;
    ml_rec.meml_damaged    := 0;
    ml_rec.meml_missing    := 0;
    ml_rec.meml_xfer_out   := 0;
    ml_rec.meml_xfer_in    := 0;

    INSERT INTO mem_line (ord_no, mem_id, pr_id, meml_qty, meml_adj, meml_rcv,
      meml_unit_price, meml_btw, meml_ex_btw) VALUES (ml_rec.ord_no, ml_rec.mem_id, 
      ml_rec.pr_id, 0, 0, 0, ml_rec.meml_unit_price, ml_rec.meml_btw,
      ml_rec.meml_ex_btw );

    RETURN ml_rec;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.open_mem_line(order_no integer, mem_no integer, pr_rec product, exc_flg boolean, exc_msg character varying) OWNER TO jes;

--
-- Name: open_mem_ord(integer, boolean, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION open_mem_ord(integer, boolean, character varying) RETURNS record
    AS $_$
  DECLARE   
    mem_no        ALIAS FOR $1; 
    exc_flg	  ALIAS FOR $2;
    exc_msg       ALIAS FOR $3;
    order_no      INTEGER;
    status	  INTEGER;
    mo_rec	  mem_order%ROWTYPE;
  BEGIN
    order_no := get_ord_no();
    SELECT INTO mo_rec * FROM mem_order WHERE ord_no = order_no AND
      mem_id = mem_no;

    IF(FOUND) THEN RETURN mo_rec; END IF;
    IF(exc_flg) THEN RAISE EXCEPTION 'open_mem_ord: %', exc_msg; END IF;
    mo_rec.ord_no                 := order_no; 
    mo_rec.mem_id                 := mem_no;
    mo_rec.memo_order_open        := LOCALTIMESTAMP;
    mo_rec.memo_amt               :=  0;
    mo_rec.mo_stgeld_rxed         :=  0;
    mo_rec.mo_stgeld_refunded     :=  0;
    mo_rec.mo_crates_rxed         :=  0;
    mo_rec.mo_crates_refunded     :=  0;
    mo_rec.mo_misc_rxed           :=  0;
    mo_rec.mo_misc_refunded       :=  0;
    mo_rec.mo_checked_out         :=  False;
    mo_rec.mo_checked_out_by      := NULL;
    status := get_ord_status();
    IF(status = 1) THEN
      mo_rec.memo_commit_open := mo_rec.memo_order_open;
    END IF;
    INSERT INTO mem_order (ord_no, mem_id, memo_order_open, memo_commit_open,
        memo_amt) VALUES (mo_rec.ord_no,
	mo_rec.mem_id, mo_rec.memo_order_open, mo_rec.memo_commit_open,
        mo_rec.memo_amt);
    RETURN mo_rec;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.open_mem_ord(integer, boolean, character varying) OWNER TO jes;

--
-- Name: open_wh_line(integer, integer, product, boolean, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION open_wh_line(integer, integer, product, boolean, character varying) RETURNS record
    AS $_$
  DECLARE   
    order_no	  ALIAS FOR $1;
    wh_no         ALIAS FOR $2;
    pr_rec	  ALIAS FOR $3; 
    exc_flg	  ALIAS FOR $4;
    exc_msg       ALIAS FOR $5;
    wl_rec	  wh_line%ROWTYPE;
  BEGIN
    SELECT INTO wl_rec * FROM wh_line WHERE ord_no = order_no AND
      wh_id = wh_no AND pr_id = pr_rec.pr_id;

    IF(FOUND) THEN RETURN wl_rec; END IF;

    IF(exc_flg) THEN RAISE EXCEPTION 'open_wl_line: %', exc_msg; END IF;
    wl_rec.ord_no          := order_no; 
    wl_rec.wh_id           := wh_no;
    wl_rec.pr_id           := pr_rec.pr_id;
    wl_rec.whl_qty	   := 0;
    wl_rec.whl_rcv	   := 0;
    wl_rec.wh_prcode	   := pr_rec.wh_prcode;
    wl_rec.whl_price	   := pr_rec.pr_wh_price;
    wl_rec.whl_btw	   := pr_rec.pr_btw;
    wl_rec.whl_mem_qty     := 0;

    INSERT INTO wh_line (ord_no, wh_id, pr_id, whl_qty, whl_rcv, wh_prcode,
      whl_price, whl_btw, whl_mem_qty) 
      VALUES (order_no, wh_no, wl_rec.pr_id,
      0, 0, wl_rec.wh_prcode, wl_rec.whl_price, wl_rec.whl_btw, 
      wl_rec.whl_mem_qty);

    RETURN wl_rec;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.open_wh_line(integer, integer, product, boolean, character varying) OWNER TO jes;

--
-- Name: open_wh_ord(integer, boolean, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION open_wh_ord(integer, boolean, character varying) RETURNS record
    AS $_$
  DECLARE   
    wh_no         ALIAS FOR $1; 
    exc_flg	  ALIAS FOR $2;
    exc_msg       ALIAS FOR $3;
    order_no      INTEGER;
    status	  INTEGER;
    wh_rec	  wh_order%ROWTYPE;
  BEGIN
    order_no := get_ord_no();
    SELECT INTO wh_rec * FROM wh_order WHERE ord_no = order_no AND
      wh_id = wh_no;

    IF(FOUND) THEN RETURN wh_rec; END IF;
    IF(exc_flg) THEN RAISE EXCEPTION 'open_wh_ord: %', exc_msg; END IF;
    wh_rec.ord_no                := order_no; 
    wh_rec.wh_id           	 := wh_no;
    wh_rec.who_order_open  	 := LOCALTIMESTAMP;
    wh_rec.who_amt_ex_btw  	 := 0;
    wh_rec.who_amt_btw           := 0;
    status := get_ord_status();
    IF(status >= 1) THEN
      wh_rec.who_commit_open := wh_rec.who_order_open;
    END IF;
    INSERT INTO wh_order (ord_no, wh_id, who_order_open, who_commit_open,
      who_amt_ex_btw, who_amt_btw)
      VALUES (wh_rec.ord_no, wh_rec.wh_id, wh_rec.who_order_open, 
        wh_rec.who_order_open, 0, 0);
    RETURN wh_rec;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.open_wh_ord(integer, boolean, character varying) OWNER TO jes;

--
-- Name: order_totals(integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION order_totals(mem integer, ord integer) RETURNS order_sums
    AS $$

    DECLARE
       mo       mem_order%ROWTYPE;
       os       order_sums;
       prod     INTEGER;
       rate     INTEGER;
       tax      INTEGER;
       prod_tot INTEGER;
       tax_tot  INTEGER;
       nr       INTEGER;
       mc       CURSOR (ODN INTEGER, MID INTEGER) FOR SELECT sum(meml_pickup * meml_ex_btw)
                   AS ex_btw, meml_btw FROM mem_line WHERE mem_id = MID and ord_no = ODN
                   GROUP BY meml_btw ORDER BY meml_btw;
    BEGIN
       os.btw_0_prods :=  0;
       os.btw_0_tax   :=  0;
       os.btw_0_rate  :=  0.0;
       os.btw_1_prods :=  0;
       os.btw_1_tax   :=  0;
       os.btw_1_rate  :=  0.0;
       os.btw_2_prods :=  0;
       os.btw_2_tax   :=  0;
       os.btw_2_rate  :=  0.0;
       os.prod_tot    :=  0;
       os.tax_tot     :=  0;
       os.grand_tot   :=  0;

       SELECT * INTO mo FROM mem_order WHERE ord_no=ord AND mem_id = mem;
       IF NOT FOUND THEN
          RETURN os;
       END IF;
       nr = 0;
       OPEN mc(ord, mem);
       LOOP 
         FETCH mc INTO prod, rate;
	 EXIT WHEN NOT FOUND;
         tax := (prod * rate * 10 + 500) / 1000;
	 os.prod_tot := os.prod_tot + prod;
         os.tax_tot  := os.tax_tot + tax; 
	 IF rate = 0.0 THEN
            os.btw_0_prods := prod;
            CONTINUE;
	 END IF;
	 nr = nr  + 1;
	 IF nr > 2 THEN
            RAISE EXCEPTION 'Order % for mem % has more than 2 BTW rates', ord, mem;
         END IF;
	 IF nr = 1 THEN
            os.btw_1_prods := prod;
	    os.btw_1_tax   := tax;
	    os.btw_1_rate  := rate;
	    CONTINUE;
         END IF;

         os.btw_2_prods := prod;
	 os.btw_2_tax   := tax;
         os.btw_2_rate  := rate;

      END LOOP;

      os.grand_tot := os.prod_tot + os.tax_tot +  mo.mo_stgeld_rxed + 
         mo.mo_crates_rxed + mo.mo_misc_rxed + mo.mo_membership 
	 - (mo.mo_stgeld_refunded + mo.mo_crates_refunded + mo.mo_misc_refunded);
      RETURN os;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.order_totals(mem integer, ord integer) OWNER TO jes;

--
-- Name: post_news(integer, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION post_news(integer, character varying) RETURNS integer
    AS $_$
  DECLARE
    poster	ALIAS FOR $1;
    body	ALIAS FOR $2;
    now		TIMESTAMP WITH TIME ZONE;
  BEGIN
    now := LOCALTIMESTAMP;
    INSERT INTO member_news (news_id, news_auth, news_date, news_text,
                             news_mod_date, news_mod_auth) VALUES (
			     nextval('member_news_news_id_seq'),
			     poster, now, body, now, poster);
    RETURN currval('member_news_news_id_seq');
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.post_news(integer, character varying) OWNER TO jes;

--
-- Name: product_update(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION product_update() RETURNS "trigger"
    AS $$
  DECLARE 
    mp INTEGER;
  BEGIN
    -- mp = minimum allowable member price
    mp := ceil(((NEW.pr_btw + 100 + NEW.pr_margin) * NEW.pr_wh_price 
          + 99)/NEW.pr_wh_q/100);

    -- only act if the member price is undefined or too low
    IF (NEW.pr_mem_price IS NULL OR NEW.pr_mem_price < mp)
        THEN
          UPDATE product SET pr_mem_price = mp, pr_changed = 't'
          WHERE pr_id = NEW.pr_id;
	  RETURN NEW;
    END IF;
    IF(((NEW.pr_mem_price != OLD.pr_mem_price) OR
        (NOT NEW.pr_active AND OLD.pr_active))
        AND NOT OLD.pr_changed)
        THEN
          UPDATE product SET pr_changed = 't'
	  WHERE pr_id = NEW.pr_id;
    END IF;
  RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.product_update() OWNER TO jes;

--
-- Name: put_dnb(character varying, character varying, character varying, character varying, character varying, character varying, numeric, integer, character varying, character varying, character varying, integer, integer, integer, integer, numeric, numeric, integer, boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean, timestamp with time zone); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION put_dnb(prcode character varying, supplier character varying, barcode character varying, descr character varying, brand character varying, kwaliteit character varying, size numeric, wh_q integer, unit character varying, land character varying, trefw character varying, col_h integer, col_g integer, vol_s integer, whpri integer, btw numeric, korting numeric, statieg integer, gluten boolean, suiker boolean, lactose boolean, milk boolean, salt boolean, soya boolean, yeast boolean, veg boolean, tstmp timestamp with time zone) RETURNS void
    AS $$

  DECLARE
    d	    dnbdata%ROWTYPE;
    do_upd  BOOLEAN := 'f';
    pr_id   INTEGER := cast(prcode as integer);
  BEGIN
    SELECT INTO d * FROM dnbdata WHERE wh_pr_id = pr_id;
    IF(FOUND) THEN
      do_upd := 't';
      -- defend against partial updates, skip records with dame or
      -- older date
      IF(d.wh_last_seen >= tstmp) THEN RETURN; END IF;

      -- do some flag fixups
      -- if it's a product, clear is_skipped
      IF(d.is_product) THEN d.is_skipped := 'f'; END IF;
      -- mark if it's changed in price, wholesale qty, btw, 
      IF(d.wh_whpri != whpri OR d.wh_wh_q != wh_q OR d.wh_btw != btw
            OR d.wh_size != size OR d.wh_unit != unit) THEN
         d.is_changed := 't';
         d.is_seen    := 'f';
      END IF;
      -- record last appearnce
      d.wh_prev_seen := d.wh_last_seen;
    ELSE
      -- new dnb product
      d.is_changed := 'f';
      d.is_seen    := 'f';
      d.is_skipped := 'f';
      d.is_product := 'f';
      d.wh_prev_seen := tstmp;
    END IF;

    d.wh_last_seen := tstmp;
    d.wh_prcode    := prcode;    d.wh_pr_id   := cast(prcode as integer);
    d.wh_supplier  := supplier;  d.wh_barcode := barcode;
    d.wh_descr     := descr;     d.wh_brand   := brand;
    d.wh_kwaliteit := kwaliteit; d.wh_size    := size;
    d.wh_wh_q      := wh_q;      d.wh_unit    := unit;
    d.wh_land      := land;      d.wh_trefw   := trefw;
    d.wh_col_h     := col_h;     d.wh_col_g   := col_g;
    d.wh_vol_s     := vol_s;     d.wh_whpri   := whpri;
    d.wh_btw       := btw;       d.wh_korting := korting;
    d.wh_statieg   := statieg;   d.wh_gluten  := gluten;
    d.wh_suiker    := suiker;    d.wh_lactose := lactose;
    d.wh_milk      := milk;      d.wh_salt    := salt;
    d.wh_soya      := soya;      d.wh_yeast   := yeast;
    d.wh_veg       := veg;
    
    IF(do_upd) THEN
       UPDATE dnbdata SET 
         wh_supplier  = supplier,     wh_barcode    = barcode,
         wh_descr     = descr,        wh_brand      = brand,
         wh_kwaliteit = kwaliteit,    wh_size       = size,
         wh_wh_q      = wh_q,         wh_unit       = unit,
         wh_land      = land,         wh_trefw      = trefw,
         wh_col_h     = col_h,        wh_col_g      = col_g,
         wh_vol_s     = vol_s,        wh_whpri      = whpri,
         wh_btw       = btw,          wh_korting    = korting,
         wh_statieg   = statieg,      wh_gluten     = gluten,
         wh_suiker    = suiker,       wh_lactose    = lactose,
         wh_milk      = milk,         wh_salt       = salt,
         wh_soya      = soya,         wh_yeast      = yeast,
         wh_veg       = veg,          is_product    = d.is_product,
         is_changed   = d.is_changed, is_seen       = d.is_seen,
         is_skipped   = d.is_skipped, wh_prev_seen  = d.wh_prev_seen,
         wh_last_seen = d.wh_last_seen
       WHERE  wh_pr_id = d.wh_pr_id;
   ELSE
         d.wh_pr_id = pr_id;
      INSERT INtO dnbdata 
        (wh_pr_id, wh_prcode, wh_supplier, wh_barcode, wh_descr, wh_brand,
         wh_kwaliteit,wh_size, wh_wh_q, wh_unit, wh_land, wh_trefw,
         wh_col_h, wh_col_g, wh_vol_s, wh_whpri,wh_btw, wh_korting,
         wh_statieg, wh_gluten, wh_suiker, wh_salt, wh_soya, wh_yeast,
         wh_veg, is_product, is_changed, is_seen, is_skipped, wh_prev_seen,
         wh_last_seen) VALUES 
        (d.wh_pr_id, d.wh_prcode, d.wh_supplier, d.wh_barcode, d.wh_descr, d.wh_brand,
         d.wh_kwaliteit,d.wh_size, d.wh_wh_q, d.wh_unit, d.wh_land, 
         d.wh_trefw, d.wh_col_h, d.wh_col_g, d.wh_vol_s, d.wh_whpri,
	 d.wh_btw, d.wh_korting, d.wh_statieg, d.wh_gluten, d.wh_suiker, 
         d.wh_salt, d.wh_soya, d.wh_yeast,  d.wh_veg, 'f', 
         'f', 'f', 'f', d.wh_prev_seen,
         d.wh_last_seen);
   END IF;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.put_dnb(prcode character varying, supplier character varying, barcode character varying, descr character varying, brand character varying, kwaliteit character varying, size numeric, wh_q integer, unit character varying, land character varying, trefw character varying, col_h integer, col_g integer, vol_s integer, whpri integer, btw numeric, korting numeric, statieg integer, gluten boolean, suiker boolean, lactose boolean, milk boolean, salt boolean, soya boolean, yeast boolean, veg boolean, tstmp timestamp with time zone) OWNER TO jes;

--
-- Name: put_zap(character varying, character varying, integer, integer, numeric, character varying, timestamp with time zone); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION put_zap(prcode character varying, descr character varying, wh_q integer, whpri integer, btw numeric, url character varying, tstmp timestamp with time zone) RETURNS void
    AS $$

  DECLARE
    d	    zapatistadata%ROWTYPE;
    do_upd  BOOLEAN := 'f';
    pr_id   INTEGER := cast(prcode as integer);
  BEGIN
    SELECT INTO d * FROM zapatistadata WHERE wh_pr_id = pr_id;
    IF(FOUND) THEN
      do_upd := 't';
      -- defend against partial updates, skip records with same or
      -- older date
      IF(d.wh_last_seen >= tstmp) THEN RETURN; END IF;

      -- do some flag fixups
      -- if it's a product, clear is_skipped
      IF(d.is_product) THEN d.is_skipped := 'f'; END IF;
      -- mark if it's changed in price, wholesale qty, btw, 
      IF(d.wh_whpri != whpri OR d.wh_wh_q != wh_q OR d.wh_btw != btw) THEN
         d.is_changed := 't';
         d.is_seen    := 'f';
      END IF;
      -- record last appearance
      d.wh_prev_seen := d.wh_last_seen;
    ELSE
      -- new zapatista product
      d.is_changed := 'f';
      d.is_seen    := 'f';
      d.is_skipped := 'f';
      d.is_product := 'f';
      d.wh_prev_seen := tstmp;
    END IF;

    d.wh_last_seen := tstmp;
    d.wh_prcode    := prcode;
    d.wh_pr_id     := cast(prcode as integer);
    d.wh_descr     := descr; 
    d.wh_wh_q      := wh_q;
    d.wh_whpri     := whpri;
    d.wh_url       := url;
    d.wh_btw       := btw;
    
    IF(do_upd) THEN
       UPDATE zapatistadata SET 
         wh_descr      = descr,
         wh_wh_q       = wh_q,
         wh_whpri      = whpri,
         wh_btw        = btw,
	 wh_url        = url,
         is_product    = d.is_product,
         is_changed    = d.is_changed, 
	 is_seen       = d.is_seen,
         is_skipped    = d.is_skipped, 
	 wh_prev_seen  = d.wh_prev_seen,
         wh_last_seen  = d.wh_last_seen
       WHERE  wh_pr_id = d.wh_pr_id;
   ELSE
         d.wh_pr_id = pr_id;
      INSERT INtO zapatistadata 
        (wh_pr_id, wh_prcode, wh_descr, 
         wh_wh_q,  wh_whpri,  wh_btw, 
         is_product, is_changed, is_seen, is_skipped, wh_prev_seen,
         wh_last_seen, wh_url) VALUES 
        (d.wh_pr_id, d.wh_prcode, d.wh_descr, 
         d.wh_wh_q, d.wh_whpri, d.wh_btw, 
         'f', 'f', 'f', 'f', d.wh_prev_seen,
         d.wh_last_seen, d.wh_url);
   END IF;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.put_zap(prcode character varying, descr character varying, wh_q integer, whpri integer, btw numeric, url character varying, tstmp timestamp with time zone) OWNER TO jes;

--
-- Name: rebuild_all_wh_headers(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION rebuild_all_wh_headers() RETURNS void
    AS $$
  DECLARE
    wh_no	INTEGER;
    order_no	INTEGER;
    wh_curs	CURSOR (ORDN INTEGER) FOR SELECT wh_id FROM wh_order
                  WHERE ord_no = ORDN;
  BEGIN
    order_no := get_ord_no();
    OPEN wh_curs(order_no);
    LOOP
      FETCH wh_curs INTO wh_no;
      EXIT WHEN NOT FOUND;
      PERFORM rebuild_wh_header(wh_no);
    END LOOP;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.rebuild_all_wh_headers() OWNER TO jes;

--
-- Name: rebuild_mem_header(integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION rebuild_mem_header(integer, integer) RETURNS void
    AS $_$
  DECLARE
  order_no	ALIAS FOR $1;
  mem_no	ALIAS FOR $2;
  delta_qty	INTEGER;
  total	INTEGER := 0;
  rcv_qty	INTEGER := 0;
  rcv_amt      	INTEGER := 0;
  l_rec		mem_line%ROWTYPE;
  h_rec		mem_order%ROWTYPE;
  litems	CURSOR (ORDN INTEGER, MEMN INTEGER) FOR 
                  SELECT * FROM mem_line WHERE ord_no = ORDN 
		  AND mem_id = MEMN;
  BEGIN
    -- get a copy of the header record
    SELECT INTO h_rec * FROM mem_order WHERE ord_no = order_no AND
      mem_id = mem_no;
    IF(NOT FOUND) THEN
      RAISE EXCEPTION 'No order % for member %', order_no, mem_no;
    END IF;
    OPEN litems(order_no, mem_no);
    LOOP
      -- look for a line item
      FETCH litems INTO l_rec;
      EXIT WHEN NOT FOUND;

      -- skip empty line items
      IF (l_rec.meml_pickup != 0) THEN
        total := total + l_rec.meml_pickup * l_rec.meml_unit_price;
      END IF;
    END LOOP;
    CLOSE litems;
    -- now update the order header.
    h_rec.memo_amt := total;
    UPDATE mem_order SET memo_amt = total
      WHERE ord_no = order_no AND mem_id = mem_no;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.rebuild_mem_header(integer, integer) OWNER TO jes;

--
-- Name: rebuild_wh_header(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION rebuild_wh_header(integer) RETURNS void
    AS $_$
  DECLARE
    wh_no	ALIAS FOR $1;
    order_no	INTEGER;
    cnt		INTEGER;
    mem_no	INTEGER;
    wh_amt	INTEGER;
    wh_btw	NUMERIC;
    wl_qty	INTEGER;
    wl_m_qty	INTEGER;
    has_order 	BOOLEAN;
    tot_m_rcv	INTEGER;
    wl_amt	INTEGER;
    wl_amt_btw	NUMERIC;
    rcv_amt	INTEGER;
    rcv_amt_btw	NUMERIC;
    rcv_qty	INTEGER;
    -- cursor for member line items, checks that member and product
    -- are both active. Assumes orders are committed
    -- retrieves the prooduct fields we'll need and the totals of the
    -- ordered (after adjustments) and delivered member orders
    ml_curs     CURSOR(ORDN INTEGER, WHN INTEGER) FOR 
                  SELECT l.pr_id, sum(l.meml_adj), sum(l.meml_rcv)
                    FROM mem_line AS l, product AS p, members AS m 
                    WHERE l.ord_no = ORDN AND p.pr_wh = WHN AND
                      m.mem_id = l.mem_id AND m.mem_active AND
                      l.pr_id = p.pr_id AND p.pr_active
                    GROUP BY l.pr_id;
    wh_rec	wh_order%ROWTYPE;      -- build wh_order header here
    wl_rec	wh_line%ROWTYPE;       -- and the wh line items here
    ml_rec	mem_line%ROWTYPE;      -- read the member line here
    oh_rec	order_header%ROWTYPE;  -- the order header itself
    pr_rec	product%ROWTYPE;
  BEGIN
    -- get a copy of the current order header for the timestamps
    SELECT INTO oh_rec * FROM order_header;
    order_no = oh_rec.ord_no;

    -- delete the wholesale line items
    DELETE FROM wh_line WHERE wh_id = wh_no AND ord_no = order_no;
    -- delete the wholesale header
    DELETE FROM wh_order WHERE wh_id = wh_no AND ord_no = order_no;
    -- see if the wholesaler is active, we're done if not
    PERFORM  * FROM wholesaler WHERE wh_id = wh_no AND wh_active;
    IF (NOT FOUND) THEN 
      RETURN; 
    END IF;

    -- Initialise some of the wholesale header and line records
    wh_rec.ord_no                := order_no;
    wl_rec.ord_no                := order_no;
    wh_rec.wh_id                 := wh_no;
    wl_rec.wh_id                 := wh_no;
    -- copy the timestamps from the order_header
    wh_rec.who_order_open        := oh_rec.oh_order_open;
    wh_rec.who_commit_open       := oh_rec.oh_commit_open;
    wh_rec.who_commit_closed     := oh_rec.oh_commit_closed;
    wh_rec.who_order_closed      := oh_rec.oh_order_closed;
    wh_rec.who_order_received    := oh_rec.oh_order_closed;
    wh_rec.who_order_completed   := oh_rec.oh_order_completed;
    wh_rec.who_amt_ex_btw        := 0;
    wh_rec.who_amt_btw           := 0;
    has_order = False;

    -- now we get the sum of all the products sold in the member line items, 
    -- one product at a time
    OPEN ml_curs(order_no, wh_no);
    LOOP
      FETCH ml_curs INTO wl_rec.pr_id, wl_rec.whl_mem_qty, tot_m_rcv;
      IF (NOT FOUND) THEN
        EXIT;
      END IF;
      SELECT INTO pr_rec * FROM product where pr_id = wl_rec.pr_id;
      IF(NOT has_order) THEN
        -- First product - create the wholesale header record
        INSERT INTO wh_order (ord_no, wh_id, who_order_open,
          who_commit_open, who_commit_closed, who_amt_ex_btw, who_amt_btw) 
          VALUES (wh_rec.ord_no, wh_rec.wh_id, wh_rec.who_order_open, 
           wh_rec.who_commit_open, wh_rec.who_commit_closed, 
	   wh_rec.who_amt_ex_btw, wh_rec.who_amt_btw);
      END IF;
      has_order := True;
      -- get size of wholesale line item order
      wl_rec.whl_qty := floor(wl_rec.whl_mem_qty / pr_rec.pr_wh_q);
      -- set received qty
      wl_rec.whl_rcv := floor(tot_m_rcv / pr_rec.pr_wh_q);
      -- calculate the wholesale order quantity and prices from the
      -- member qty
      wl_amt         := wl_rec.whl_qty * pr_rec.pr_wh_price;
      wl_amt_btw     := wl_rec.whl_qty * pr_rec.pr_wh_price * 
                        (100 + pr_rec.pr_btw);
      -- same for the received quantity 
      rcv_qty        := floor(tot_m_rcv / pr_rec.pr_wh_q);
      rcv_amt 	     := rcv_qty * pr_rec.pr_wh_price;
      rcv_amt_btw    := rcv_qty * pr_rec.pr_wh_price * (100 + pr_rec.pr_btw);
      -- save the wholesale price, the wholesaler''s product code 
      -- and the btw rate 
      wl_rec.wh_prcode  := pr_rec.wh_prcode;
      wl_rec.whl_price  := pr_rec.pr_wh_price;
      wl_rec.whl_btw    := pr_rec.pr_btw;
      -- update the header with the various amounts for this line
      wh_rec.who_amt_ex_btw := wh_rec.who_amt_ex_btw + wl_amt;
      wh_rec.who_amt_btw := wh_rec.who_amt_btw + wl_amt_btw;
      -- add the line item to the wholesale order
      INSERT INTO wh_line (ord_no, wh_id, pr_id, whl_qty, whl_rcv,
        wh_prcode, whl_price, whl_btw, whl_mem_qty) VALUES
	(wl_rec.ord_no, wl_rec.wh_id, wl_rec.pr_id, wl_rec.whl_qty, 
         wl_rec.whl_rcv, wl_rec.wh_prcode, wl_rec.whl_price, wl_rec.whl_btw, 
         wl_rec.whl_mem_qty);
    END LOOP;
    CLOSE ml_curs;

    IF(has_order) THEN
      UPDATE wh_order SET  
	who_order_open = wh_rec.who_order_open,
	who_commit_open = wh_rec.who_commit_open, 
        who_commit_closed = wh_rec.who_commit_closed, 
	who_amt_ex_btw = wh_rec.who_amt_ex_btw, 
	who_amt_btw = wh_rec.who_amt_btw WHERE
	ord_no = wh_rec.ord_no AND wh_id = wh_rec.wh_id;
    END IF;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.rebuild_wh_header(integer) OWNER TO jes;

--
-- Name: remove_inactive_member_order(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION remove_inactive_member_order(integer) RETURNS void
    AS $_$
  DECLARE
    mem_no	ALIAS FOR $1;
    order_no	INTEGER;
    cnt		INTEGER;
    status	INTEGER;
  BEGIN
    order_no := get_ord_no();
    status   := get_ord_status();
    SELECT INTO cnt count(*) FROM mem_line AS l, product AS p WHERE
    l.ord_no = order_no AND l.mem_id = l.mem_id  AND p.pr_active AND
    l.pr_id = p.pr_id;
    IF(cnt > 0 AND status >= 4) THEN 
      RAISE EXCEPTION 'Member has committed order';
    END IF;
    DELETE FROM mem_line WHERE ord_no = order_no AND mem_id = mem_no;
    DELETE FROM mem_order WHERE ord_no = order_no AND mem_id = mem_no;
    PERFORM rebuild_all_wh_headers();

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.remove_inactive_member_order(integer) OWNER TO jes;

--
-- Name: remove_product(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION remove_product(integer) RETURNS boolean
    AS $_$
  DECLARE
    pr_no	ALIAS FOR $1;
    order_no	INTEGER;
    mem_no	INTEGER;
    wh_no	INTEGER;
    mitems	CURSOR (ODN INTEGER, PID INTEGER) FOR SELECT mem_id FROM
                  mem_line WHERE ord_no = ODN AND pr_id = PID;
    witems	CURSOR (ODN INTEGER, PID INTEGER) FOR SELECT wh_id FROM
                  wh_line WHERE ord_no = ODN AND pr_id = PID;
  BEGIN
    -- do not remove a completed order
    IF(get_ord_status() >= 4) THEN RETURN False; END IF;
    order_no := get_ord_no();
    OPEN mitems(order_no, pr_no);
    LOOP
      -- find any line items for product and delete them
      FETCH mitems INTO mem_no;
      EXIT WHEN NOT FOUND;

      DELETE FROM mem_line WHERE pr_id = pr_no AND ord_no = order_no
        AND mem_id = mem_no;
      -- then fix the header totals
      PERFORM rebuild_mem_header(order_no, mem_no);
    END LOOP;
    CLOSE mitems;
    OPEN witems(order_no, pr_no);
    LOOP
       -- find any wholesale line itmes for product and delete them
      FETCH witems INTO wh_no;
      EXIT WHEN NOT FOUND;
      DELETE FROM wh_line WHERE pr_id = pr_no AND ord_no = order_no AND
        wh_id = wh_no;
      PERFORM update_wh_header(wh_no);
    END LOOP;
    CLOSE witems;
    RETURN True;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.remove_product(integer) OWNER TO jes;

--
-- Name: remove_wholesaler(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION remove_wholesaler(integer) RETURNS void
    AS $_$
  DECLARE
    wh_no	ALIAS FOR $1;
    order_no	INTEGER;
    mem_no	INTEGER;
    pr_no	INTEGER;
    mitems	CURSOR (ODN INTEGER, WHN INTEGER) 
      FOR SELECT mem_id FROM mem_line AS m, product AS p 
        WHERE m.ord_no = ODN AND m.pr_id = p.pr_id
           AND p.pr_wh = WHN;
  BEGIN
    -- do not remove a completed order
    IF(get_ord_status() >= 5) THEN RETURN; END IF;
    order_no := get_ord_no();
    OPEN mitems(order_no, wh_no);
    LOOP
      -- find any line items for wholesaler and delete them
      FETCH mitems INTO mem_no;
      EXIT WHEN NOT FOUND;
      -- ** report removal code = 1 wholesaler dropped
      DELETE FROM mem_line WHERE pr_id = pr_no AND ord_no = order_no
        AND mem_id = mem_no;
      -- then fix the header totals
      PERFORM rebuild_mem_header(order_no, mem_no);
    END LOOP;
    CLOSE mitems;
    -- remove the wholesale order details
    DELETE FROM wh_line WHERE wh_id = wh_no AND ord_no = order_no;
    DELETE FROM wh_order WHERE wh_id = wh_no AND ord_no = order_no;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.remove_wholesaler(integer) OWNER TO jes;

--
-- Name: set_adm_adj(integer, boolean); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_adm_adj(integer, boolean) RETURNS void
    AS $_$
  DECLARE
    mem_no	ALIAS FOR $1;
    is_adm	ALIAS FOR $2;
  BEGIN
    UPDATE members SET mem_adm_adj = is_adm WHERE mem_id = mem_no;

END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_adm_adj(integer, boolean) OWNER TO jes;

--
-- Name: set_member_price(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_member_price() RETURNS "trigger"
    AS $$
  DECLARE 
    mp INTEGER;
  BEGIN
    -- mp = minimum allowable member price
    mp := ceil(((NEW.pr_btw + 100 + NEW.pr_margin) * NEW.pr_wh_price 
          + 99)/NEW.pr_wh_q/100);

    -- only act if the member price is undefined or too low
    IF (NEW.pr_mem_price IS NULL OR NEW.pr_mem_price < mp)
      THEN
        NEW.pr_mem_price := mp;
    END IF;
    IF NEW.pr_ex_btw IS NULL
       THEN
          NEW.pr_ex_btw = ex_btw_prc(NEW.pr_mem_price, NEW.pr_btw);
     END IF;
  RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_member_price() OWNER TO jes;

--
-- Name: set_status_0(character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_0(character varying) RETURNS integer
    AS $_$
  DECLARE
    order_label	ALIAS FOR $1;
    order_no	INTEGER;
    mem_no	INTEGER;
    def_rec	default_order%ROWTYPE;
    pr_no	INTEGER;
    quantity	INTEGER;
    df_curs	CURSOR FOR SELECT d.mem_id, d.pr_id, d.qty
    		  FROM members AS m, default_order AS d, product AS p
		  WHERE m.mem_id = d.mem_id AND mem_active AND 
		  p.pr_id = d.pr_id AND p.pr_active;
    co_curs	CURSOR FOR SELECT c.mem_id, c.pr_id, c.qty
    		  FROM members AS m, carry_over AS c, product AS p
		  WHERE m.mem_id = c.mem_id AND mem_active AND 
		  p.pr_id = c.pr_id AND p.pr_active;
  BEGIN
    order_no := get_ord_no();
    IF(get_ord_status() != 7) THEN 
       RAISE EXCEPTION 'Current order % is not completed', order_no;
    END IF;

    DELETE FROM email_changes;
    DELETE FROM email_status_changes;
    UPDATE product set pr_changed = 'f', pr_mq_chg = 'f' WHERE
      pr_changed OR pr_mq_chg;

    UPDATE order_header SET ord_label = order_label, ord_status = 0, 
      func_flag = False WHERE mas_key = 1;
    -- install default orders
    order_no = get_ord_no();
    open df_curs;
    LOOP
      FETCH df_curs INTO mem_no, pr_no, quantity;
      EXIT WHEN NOT FOUND;
      PERFORM add_order_to_member(pr_no, quantity, mem_no, 0);
    END LOOP;
    CLOSE df_curs;
    OPEN co_curs;
    LOOP
      FETCH co_curs INTO mem_no, pr_no, quantity;
      EXIT WHEN NOT FOUND;
      PERFORM add_order_to_member(pr_no, quantity, mem_no, 0);
    END LOOP;
    CLOSE co_curs;
    RETURN 0;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_0(character varying) OWNER TO jes;

--
-- Name: set_status_1(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_1() RETURNS void
    AS $$
  DECLARE
    order_no	INTEGER;
  BEGIN 
    order_no := get_ord_no();
    UPDATE order_header SET ord_status = 1, func_flag = False WHERE mas_key = 1;
    UPDATE mem_order SET memo_commit_open = LOCALTIMESTAMP 
       WHERE ord_no = order_no;
    UPDATE wh_order SET who_commit_open = LOCALTIMESTAMP
       WHERE ord_no = order_no;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_1() OWNER TO jes;

--
-- Name: set_status_2(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_2() RETURNS void
    AS $$
  DECLARE
    order_no	INTEGER;
  BEGIN 
    order_no := get_ord_no();
    UPDATE order_header SET ord_status = 2, func_flag = False WHERE mas_key = 1;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_2() OWNER TO jes;

--
-- Name: set_status_2(boolean); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_2(boolean) RETURNS integer
    AS $_$
  DECLARE
    force     ALIAS FOR $1;
    order_no  INTEGER;
    cnt	      INTEGER;
    mem_no    INTEGER;
    wh_no     INTEGER;
    -- cursor for uncommitted orders
    mu_curs   CURSOR (ORDN INTEGER) FOR SELECT mem_id FROM mem_order 
    		   WHERE ord_no = ORDN AND memo_commit_closed IS NULL;
    -- cursor for committed orders
    mc_curs   CURSOR (ORDN INTEGER) FOR SELECT mem_id FROM mem_order 
    		   WHERE ord_no = ORDN;
    -- cursor for wholesaler numbers
    wh_curs   CURSOR FOR SELECT wh_id FROM wholesaler
                WHERE wh_active;
    -- cursor for member line items
    ml_curs   CURSOR(ORDN INTEGER, WHON INTEGER) FOR SELECT pr_id, 
                sum(meml_qty) FROM member_line 
                WHERE ord_no = ORDN AND wh_id = WHON
                GROUP BY pr_id;
   BEGIN
      order_no := get_ord_no();
      IF(NOT force) THEN
         -- see if all the orders are committed
         SELECT INTO cnt count(*) FROM mem_order WHERE ord_no = order_no AND
            memo_commit_closed IS NULL AND memo_amt != 0;
         IF(cnt != 0) THEN RETURN cnt; END IF;
      END IF;
      DELETE FROM email_notices WHERE notify_ty = 3;
      -- clear all carry_overs
      DELETE FROM carry_over;
      -- forcibly discard uncommitted orders, while saving their orders
      OPEN mu_curs(order_no);
      LOOP
         FETCH mu_curs INTO mem_no;
	 EXIT WHEN NOT FOUND;
	 INSERT INTO email_notices (mem_id, notify_ty) VALUES (mem_no, 3);
	 PERFORM create_carry_over(mem_no);
      END LOOP;
      CLOSE mu_curs;

      DELETE FROM mem_line  WHERE ord_no = order_no AND mem_id IN (
        SELECT m.mem_id FROM mem_order AS m WHERE ord_no = order_no AND
	  memo_commit_closed IS NULL);
      DELETE FROM mem_order WHERE ord_no = order_no AND
         memo_commit_closed IS NULL;

      -- for each wholesaler
      OPEN wh_curs;
      LOOP
        FETCH wh_curs INTO wh_no;
	EXIT WHEN NOT FOUND;
        PERFORM rebuild_wh_header(wh_no);
      END LOOP;
      CLOSE wh_curs;
      UPDATE order_header SET ord_status = 2, func_flag = False 
      	     WHERE mas_key = 1;
      RETURN 0;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_2(boolean) OWNER TO jes;

--
-- Name: set_status_3(boolean); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_3(boolean) RETURNS integer
    AS $_$
   DECLARE
      force	ALIAS FOR $1;    -- True if we discard uncommitted orders
      order_no	INTEGER;
      cnt	INTEGER;
      mem_no	INTEGER;
      wh_no	INTEGER;
      -- cursor for uncommitted orders
      mu_curs   CURSOR (ORDN INTEGER) FOR SELECT mem_id FROM mem_order 
      		   WHERE ord_no = ORDN AND memo_commit_closed IS NULL;
      -- cursor for committed orders
      mc_curs   CURSOR (ORDN INTEGER) FOR SELECT mem_id FROM mem_order 
      		   WHERE ord_no = ORDN;
      -- cursor for wholesaler numbers
      wh_curs   CURSOR FOR SELECT wh_id FROM wholesaler
                  WHERE wh_active;
      -- cursor for member line items
      ml_curs   CURSOR(ORDN INTEGER, WHON INTEGER) FOR SELECT pr_id, 
                  sum(meml_qty) FROM member_line 
                  WHERE ord_no = ORDN AND wh_id = WHON
                  GROUP BY pr_id;
   BEGIN
      order_no := get_ord_no();
      IF(NOT force) THEN
         -- see if all the orders are committed
         SELECT INTO cnt count(*) FROM mem_order WHERE ord_no = order_no AND
            memo_commit_closed IS NULL AND memo_amt != 0;
         IF(cnt != 0) THEN RETURN cnt; END IF;
      END IF;
      -- clear all carry_overs
      DELETE FROM carry_over;
      -- forcibly discard uncommitted orders, while saving their orders
      OPEN mu_curs(order_no);
      LOOP
         FETCH mu_curs INTO mem_no;
	 EXIT WHEN NOT FOUND;
	 PERFORM create_carry_over(mem_no);
      END LOOP;
      CLOSE mu_curs;

      DELETE FROM mem_line  WHERE ord_no = order_no AND mem_id IN (
        SELECT m.mem_id FROM mem_order AS m WHERE ord_no = order_no AND
	  memo_commit_closed IS NULL);
      DELETE FROM mem_order WHERE ord_no = order_no AND
         memo_commit_closed IS NULL;

      -- for each wholesaler
      OPEN wh_curs;
      LOOP
        FETCH wh_curs INTO wh_no;
	EXIT WHEN NOT FOUND;
        PERFORM rebuild_wh_header(wh_no);
      END LOOP;
      close wh_curs;
      UPDATE order_header SET ord_status = 3, func_flag = False 
        WHERE mas_key = 1;
      RETURN 0;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_3(boolean) OWNER TO jes;

--
-- Name: set_status_3(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_3() RETURNS void
    AS $$
    BEGIN
      UPDATE order_header SET ord_status = 3, func_flag = False 
        WHERE mas_key = 1;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_3() OWNER TO jes;

--
-- Name: set_status_4(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_4() RETURNS integer
    AS $$ -- TESTED
  DECLARE 
    order_no	INTEGER;
    cnt		INTEGER;
  BEGIN
    order_no := get_ord_no();
    cnt := count_all_shortages();
    IF(cnt != 0) THEN RETURN cnt; END IF;
    UPDATE order_header SET ord_status = 4, func_flag = false  WHERE mas_key = 1;
    RETURN 0;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_4() OWNER TO jes;

--
-- Name: set_status_5(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_5() RETURNS integer
    AS $$
  DECLARE 
    order_no	INTEGER;
  BEGIN
    order_no := get_ord_no();
    UPDATE order_header SET ord_status = 5, func_flag = False WHERE mas_key = 1;
    RETURN 0;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_5() OWNER TO jes;

--
-- Name: set_status_6(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_6() RETURNS integer
    AS $$
  DECLARE 
    order_no	INTEGER;
  BEGIN
    order_no := get_ord_no();
    UPDATE order_header SET ord_status = 6, func_flag = False WHERE mas_key = 1;
    RETURN 0;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_6() OWNER TO jes;

--
-- Name: set_status_7(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION set_status_7() RETURNS integer
    AS $$ 
  DECLARE
    order_no    INTEGER;
    cnt         INTEGER;
    p		product%ROWTYPE;
    pr_items	CURSOR (ODN INTEGER) FOR SELECT * FROM product
                  WHERE pr_id IN (SELECT pr_id FROM wh_line WHERE
                     ord_no = ODN);
  BEGIN
    order_no := get_ord_no();
    cnt := count_all_rcv_shortages();
    IF(cnt != 0) THEN RETURN cnt; END IF;
    -- initialise pickup amounts, ensure prices and btw are up-to-date    
    OPEN pr_items(order_no);
    LOOP
      FETCH pr_items INTO p;
      EXIT WHEN NOT FOUND;
      UPDATE mem_line SET meml_pickup = meml_rcv, meml_ex_btw = p.pr_ex_btw, 
         meml_unit_price = p.pr_mem_price, meml_btw = p.pr_btw WHERE
	 ord_no = order_no and pr_id = p.pr_id;
    END LOOP;
    UPDATE order_header SET ord_status = 7, func_flag = False WHERE mas_key = 1;
    RETURN 0;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.set_status_7() OWNER TO jes;

--
-- Name: short(integer, integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION short(integer, integer, integer) RETURNS integer
    AS $_$
  declare
    qty alias for $1;
    ord alias for $2;
    siz alias for $3;
    tot integer;
  begin
    tot := qty - ord;
    if(tot >= 0) then return tot; end if;
    return siz + tot;
end;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.short(integer, integer, integer) OWNER TO jes;

--
-- Name: status_change(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION status_change() RETURNS "trigger"
    AS $$
  DECLARE 
    new_ord_no		INTEGER;
    old_ord_no		INTEGER;
    new_ff		BOOLEAN;
    old_ff		BOOLEAN;
  BEGIN
    new_ord_no := NEW.ord_no ;
    old_ord_no := OLD.ord_no;
    new_ff = NEW.func_flag;
    old_ff = OLD.func_flag;
    IF(NEW.func_flag) THEN RETURN NULL; END IF;
    IF(OLD.ord_status = 7 AND NEW.ord_status = 0) THEN
      new_ord_no := OLD.ord_no + 1;
      UPDATE order_header 
        SET ord_no = new_ord_no, oh_order_open = LOCALTIMESTAMP,
           oh_commit_open = NULL, oh_commit_closed = NULL,
	   oh_order_closed = NULL, oh_order_received = NULL,
	   oh_order_completed = NULL, func_flag = True;
      RETURN NEW;
    END IF;
    IF(OLD.ord_status + 1 != NEW.ord_status OR NEW.ord_status > 7) THEN
      UPDATE order_header 
         SET ord_status = OLD.ord_status, ord_no = OLD.ord_no,
             func_flag = True;
      RETURN NEW;
    END IF;
    UPDATE wh_order SET ord_label=NEW.ord_label WHERE ord_no = NEW.ord_no;
    UPDATE mem_order SET ord_label=NEW.ord_label WHERE ord_no = NEW.ord_no;
    IF(NEW.ord_status = 1) THEN
      UPDATE order_header 
        SET oh_commit_open = LOCALTIMESTAMP, func_flag = True;
    ELSIF(NEW.ord_status = 3) THEN
      UPDATE wh_order SET who_commit_closed = LOCALTIMESTAMP
        WHERE ord_no = OLD.ord_no;
      UPDATE order_header 
        SET oh_commit_closed = LOCALTIMESTAMP, func_flag = True;
    ELSIF(NEW.ord_status = 4) THEN
      UPDATE mem_order SET memo_closed = LOCALTIMESTAMP
        WHERE ord_no = OLD.ord_no;
      UPDATE wh_order SET who_order_closed = LOCALTIMESTAMP
        WHERE ord_no = OLD.ord_no;
      UPDATE order_header 
        SET oh_order_closed = LOCALTIMESTAMP, func_flag = True;
    ELSIF(NEW.ord_status = 5) THEN
      UPDATE wh_order SET who_order_received = LOCALTIMESTAMP
        WHERE ord_no = OLD.ord_no;
      UPDATE order_header 
        SET oh_order_received = LOCALTIMESTAMP, func_flag = True;
    ELSIF(NEW.ord_status = 6) THEN
      UPDATE mem_order SET memo_order_received = LOCALTIMESTAMP
         WHERE ord_no = OLD.ord_no;
    ELSIF(NEW.ord_status = 7) THEN
      UPDATE mem_order SET memo_completed = LOCALTIMESTAMP
         WHERE ord_no = OLD.ord_no;
      UPDATE wh_order SET who_order_completed = LOCALTIMESTAMP
         WHERE ord_no = OLD.ord_no;
      UPDATE order_header 
        SET oh_order_completed = LOCALTIMESTAMP, func_flag = True;
    END IF;
    RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.status_change() OWNER TO jes;

--
-- Name: update_member_price(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION update_member_price() RETURNS "trigger"
    AS $$
  DECLARE 
    mp          INTEGER;
    ex_btw_mp   INTEGER;
    btw         NUMERIC;
  BEGIN
    btw = NEW.pr_btw;
    -- mp = minimum allowable member price
    mp := min_price(NEW.pr_wh_price, NEW.pr_btw, NEW.pr_margin,
                    NEW.pr_wh_q);
    -- get the corresponding  ex-btw price 
    ex_btw_mp := ex_btw_prc(mp, btw);
    -- the ex-btw price may force a with-btw price change
    mp := btw_price(ex_btw_mp, btw);
    -- only act if the member price is undefined or too low
    IF (NEW.pr_mem_price IS NULL OR NEW.pr_mem_price < mp)
       THEN
         NEW.pr_mem_price := mp;
         NEW.pr_ex_btw    := ex_btw_mp;
	 NEW.pr_changed = 't';
       ELSE
         -- check that we have a valid ex_btw price and btw
        NEW.pr_ex_btw := ex_btw_prc(NEW.pr_mem_price, btw);
        NEW.pr_mem_price = btw_price(NEW.pr_ex_btw, btw);
    end IF;

    IF((NEW.pr_mem_price != OLD.pr_mem_price) OR
        (NEW.pr_ex_btw   != OLD.pr_ex_btw)    OR
	(NEW.pr_mem_q    != OLD.pr_mem_q)     OR
        (NEW.pr_wh_q     != OLD.pr_wh_q)      OR
	(NEW.pr_wh_price != OLD.pr_wh_price)  OR
	(NEW.pr_btw      != OLD.pr_btw)       OR
        (NOT NEW.pr_active AND OLD.pr_active))
       THEN
          NEW.pr_changed = 't';
    END IF;
  RETURN NEW;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.update_member_price() OWNER TO jes;

--
-- Name: update_news(integer, integer, character varying); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION update_news(integer, integer, character varying) RETURNS integer
    AS $_$
  DECLARE
    nid		ALIAS FOR $1;
    poster	ALIAS FOR $2;
    body	ALIAS FOR $3;
    now		TIMESTAMP WITH TIME ZONE;
  BEGIN
    now := LOCALTIMESTAMP;
    UPDATE member_news SET news_text = body,
                         news_mod_date = now, 
			   news_mod_auth = poster
    WHERE news_id = nid;
    RETURN 1;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.update_news(integer, integer, character varying) OWNER TO jes;

--
-- Name: update_wh_header(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION update_wh_header(integer) RETURNS boolean
    AS $_$
  DECLARE
    wh_no	 ALIAS FOR $1;
    order_no     INTEGER;
    result	 BOOLEAN := False;
    delta_qty	 INTEGER;         -- line item wh. order qt
    tot_ex_btw   INTEGER := 0;    -- order total, ex btw
    tot_btw      NUMERIC := 0;    -- order total, inc btw
    wh_rec	 wh_order%ROWTYPE;
    wl_rec	 wh_line%ROWTYPE;
    pr_rec	 product%ROWTYPE;
    -- cursor to go through wholesale order line items
    litems	 CURSOR (ORDN INTEGER, WHN INTEGER) FOR SELECT * 
                   FROM wh_line WHERE ord_no = ORDN AND wh_id = WHN;
  BEGIN
    order_no := get_ord_no();
    SELECT INTO wh_rec * FROM wh_order WHERE ord_no = order_no AND
      wh_id = wh_no;
    IF(NOT FOUND) THEN
       RETURN False;
    END IF;
    OPEN litems(order_no, wh_no);
    -- get the current values
    LOOP
      -- do every line item for this wholesale order
      FETCH litems INTO wl_rec;
      EXIT WHEN NOT FOUND;

      -- delete empty line items
      IF(wl_rec.whl_qty = 0) THEN 
	DELETE FROM wh_line WHERE ord_no = order_no AND wh_id = wh_no
	  AND pr_id = wl_rec.pr_id;
      ELSE
        -- go get the prices from the product, skip inactive products
        SELECT INTO pr_rec * FROM product 
	  WHERE pr_id = wl_rec.pr_id AND pr_active;
        IF NOT FOUND THEN
	  RAISE EXCEPTION 'product % in line items, not found or inactive',
	    wl_rec.pr_id;
        END IF;         
        -- calculate wholesale details using product table details instead
        -- of line item details
        delta_qty := wl_rec.whl_qty - wl_rec.whl_rcv;
        tot_ex_btw := tot_ex_btw + wl_rec.whl_qty * pr_rec.pr_wh_price;
        tot_btw := tot_btw + (wl_rec.whl_qty * pr_rec.pr_wh_price *
  	           (100 + pr_rec.pr_btw));
        -- update the line item if the price has changed
        IF(wl_rec.whl_btw != pr_rec.pr_btw OR 
	     wl_rec.whl_price != pr_rec.pr_wh_price) THEN
    	  result := True;
          UPDATE wh_line SET whl_btw = pr_rec.pr_btw, 
            whl_price = pr_rec.pr_wh_price
            WHERE ord_no = order_no AND wh_id = wh_no 
	      AND pr_id = pr_rec.pr_id;
        END IF;
      END IF;
    END LOOP;
    CLOSE litems;
    -- now update the order header. 
    tot_btw := tot_btw;
    IF(wh_rec.who_amt_ex_btw != tot_ex_btw OR 
      wh_rec.who_amt_btw != tot_btw) THEN
      RAISE NOTICE 'update_wh_header %:% amt_ex_btw % -> % amt_btw % -> % ',
        order_no, wh_no, 
        wh_rec.who_amt_ex_btw, tot_ex_btw, 
        wh_rec.who_amt_btw, tot_btw;

      UPDATE wh_order SET who_amt_ex_btw = tot_ex_btw,
        who_amt_btw = tot_btw
	WHERE ord_no = order_no AND wh_id = wh_no;
      result = True;
    END IF;
    RETURN result;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.update_wh_header(integer) OWNER TO jes;

--
-- Name: update_wh_line_items(integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION update_wh_line_items(integer) RETURNS boolean
    AS $_$
   DECLARE
      wh_no     ALIAS FOR $1;
      order_no  INTEGER;
      cnt       INTEGER;
      p_id	INTEGER;
      l_qty	INTEGER;         -- sum of mem orders for p_id
      r_qty	INTEGER;	 -- sum of not-delivered mem items
      w_qty	INTEGER;
      delta_m	INTEGER;	 -- not delivered member quantity of p_id
      delta_w	INTEGER;	 -- not delivered wholesale qty of p_id
      tot_ex	INTEGER := 0;
      tot_btw	NUMERIC := 0;
      result	BOOLEAN := False;
      pr_rec	product%ROWTYPE;
      wh_rec	wh_order%ROWTYPE;
      wl_rec	wh_line%ROWTYPE;
      -- cursor to find entries in wh_line items table
      litems	CURSOR(ORDN INTEGER, WHN INTEGER) FOR
      		SELECT * FROM wh_line WHERE ord_no = ODN AND wh_id = WHN;
      -- cursor to find items in mem_line table
      pitems    CURSOR(ORDN INTEGER, WHN INTEGER) FOR
                SELECT p.pr_id, sum(l.meml_adj), sum(l.mel_rcv)
                FROM product AS p, members AS m, mem_line AS l
                WHERE p.pr_active AND m.mem_active AND 
                p.pr_id = l.pr_id AND p.pr_wh = WHN AND l.mem_id = m.mem_id
                AND l.meml_qty != 0 GROUP BY pr_id;
   BEGIN
      order_no := get_ord_no();
      SELECT INTO wh_rec * FROM wh_order 
              WHERE ord_no = order_no AND wh_id = wh_no;
      IF(NOT FOUND) THEN
          RETURN False;
      END IF;
      OPEN litems(ord_no, wh_no);
     -- make sure that every member line item appears in the 
     -- wholesale line items
     OPEN pitems(ord_no, wh_no);
     LOOP
       -- get product code and quantity for member orders
       FETCH pitems into p_id, l_qty, r_qty;
       -- get the product record (we need the wholesale qty)
       SELECT INTO pr_rec * FROM product WHERE pr_id = p_id;
       -- convert member order qty to wholesale qty
       w_qty := floor(l_qty/pr_rec.pr_wh_q);
       -- qty not delivered of member orders
       delta_m := r_qty - l_qty;
       -- which converts into qty not delivered of wholesaler orders
       delta_w := floor(delta_m / pr_rec.pr_wh_q);
       -- calculate wholesale order with and without btw
       tot_ex := tot_ex + w_qty * pr_rec.pr_wh_price;
       tot_btw := tot_btw + w_qty * pr_rec.pr_wh_price * (100 + pr_rec.pr_btw);

       -- see if there is a line item for this product,
       -- create one if not
       SELECT INTO wl_rec * FROM wh_line WHERE ord_no = order_no AND
	 wh_id = wh_no;
       IF(NOT FOUND) THEN
	 INSERT INTO wh_line (ord_no, wh_id, pr_id, whl_q, wh_rcv, wh_prcode,
	   whl_prcode, whl_price, whl_btw, whl_mem_qty) VALUES 
            (order_no, wh_no, pr_rec.pr_id, w_qty, floor(r_qty/pr_rec.pr_wh_q),
             pr_rec.wh_prcode, pr_rec.pr_wh_price, pr_rec.pr_btw, l_qty);
	 result := True;
       END IF;
     END LOOP;
     CLOSE pitems;
     -- the above checked that every member line item is represented
     -- in the wholesale order. Now ensure that there are no wholesale
     -- line items with no matching member line items
     LOOP
        -- check existing items in wh_line table
        FETCH litems INTO wl_rec;
	EXIT WHEN NOT FOUND;
	-- see what the quantity should be. meml_adj is either
        -- original or adjusted quantity
	SELECT INTO l_qty sum(l.meml_adj)  
  	  FROM product AS p, members AS m, mem_line AS l
          WHERE p.pr_active AND m.mem_active AND p.pr_id = wl_rec.pr_id AND
          p.pr_id = l.pr_id AND p.pr_wh = wh_no AND l.mem_id = m.mem_id AND 
          l.ord_no = order_no;
        -- delete line items without any member orders
	IF(NOT FOUND OR l_qty = 0) THEN
	  DELETE FROM wh_line WHERE ord_no = order_no AND wh_id = wh_no 
	    AND pr_id = p_id;
	  result := True;
	  CONTINUE;
	END IF;
	-- check that line item matches product item
	SELECT INTO pr_rec * FROM product WHERE pr_id = wl_rec.pr_id;
	IF(wl_rec.whl_qty = floor(l_qty/pr_rec.pr_wh_q) AND 
           wl_rec.wh_prcode = pr_rec.wh_prcode AND 
	   wl_rec.whl_price = pr_rec.pr_wh_price AND 
           wl_rec.whl_btw = pr_rec.pr_btw AND 
           wl_rec.whl_rcv = floor(r_qty/pr_rec.pr_wh_q)) THEN 
	   CONTINUE;
	END IF;
        UPDATE wh_line SET whl_qty = w_qty, 
          whl_btw = pr_rec.pr_btw,  wh_prcode = pr_rec.wh_prcode,
          whl_price = pr_rec.pr_wh_price, 
          whl_rcv = floor(r_qty/pr_rec.pr_wh_q) 
	  WHERE ord_no = order_no AND wh_id = wh_no AND pr_id = wl_rec.pr_id;
	result = True;
     END LOOP;
     CLOSE litems;
     tot_btw  = tot_btw;
     -- now see if there are any line items left
     SELECT INTO cnt count(*) FROM wh_line WHERE ord_no = order_no AND
        wh_id = wh_no;
     IF(cnt = 0) THEN
        DELETE FROM wh_order WHERE ord_no = order_no AND wh_id = wh_no;
        result = True;
     END IF;
     -- now see if the header needs updating
     IF(wh_rec.who_amt_ex_btw != tot_ex OR 
        wh_rec.who_amt_btw != tot_btw) THEN
        UPDATE wh_order SET who_amt_ex_btw = tot_ex, 
           who_amt_btw = tot_btw 
              WHERE ord_no = order_no AND wh_id = wh_no;
	result = True;
     END IF;
     RETURN result;
END;$_$
    LANGUAGE plpgsql;


ALTER FUNCTION public.update_wh_line_items(integer) OWNER TO jes;

--
-- Name: xfer_order(integer, integer, integer, integer, integer); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION xfer_order(from_mem_id integer, to_mem_id integer, ord_num integer, pr_num integer, xfr_qty integer) RETURNS void
    AS $$
   DECLARE
     order_no       INTEGER;
     status         INTEGER;
     ml_from	    mem_line%ROWTYPE;
     ml_to	    mem_line%ROWTYPE;
     pr_rec         product%ROWTYPE;
     xfr_rec        xfer%ROWTYPE;
     delta	    INTEGER;
     is_checked_out BOOLEAN;
   BEGIN
     -- looK for reasons not to do anything or to complain
     -- skip transfers from self to self
     IF to_mem_id = from_mem_id THEN RETURN; END IF;

     order_no := get_ord_no();
     status   := get_ord_status();
     -- requires a valid order number
     IF ord_num > order_no THEN
        RAISE EXCEPTION 'Invalid order number %', ord_no;
     END IF;
     -- current order only allows this at phase 7 (ready for pickup)
     IF order_no = ord_num AND status < 7 THEN
        RAISE EXCEPTION 'This order is not at the pickup stage';
     END IF;

     -- get the source
     SELECT * INTO ml_from FROM mem_line WHERE mem_id = from_mem_id AND
        ord_no = ord_num AND pr_id = pr_num;
     IF NOT FOUND THEN
        RAISE EXCEPTION 'Can''t find order for product % by  member %',
          pr_num,  from_mem_id;
     END IF;

     -- Finally, check that we aren't trying to transfer through to a third
     -- party
     IF ml_from.meml_xfer_in != 0 AND xfr_qty != 0 THEN
        RAISE EXCEPTION 'Can''t transfer items both to and from order for member %',
	  from_mem_id;
     END IF;

     SELECT * INTO pr_rec FROM product WHERE pr_id = pr_num;
     IF NOT FOUND THEN
        RAISE EXCEPTION 'Can''t find product record for pr_id %', pr_num;     
     END IF;

     -- find any previous transfer in this direction
     SELECT * INTO xfr_rec FROM xfer WHERE from_id = from_mem_id AND
        to_id = to_mem_id AND ord_no = ord_num AND pr_id = pr_num;
     IF NOT FOUND THEN
        -- 0 qty and nothing to change, we can stop here
        IF xfr_qty = 0 THEN RETURN; END IF;
	-- first transfer, is there enough there to fill the request?
	IF xfr_qty > ml_from.meml_pickup THEN
           RAISE EXCEPTION 'Can''t transfer % items of product % from member %',
              xfr_qty, pr_num, from_mem_id;
        END IF;
	-- set up the xfer record and insert it
        xfr_rec.from_id := from_mem_id;
        xfr_rec.to_id   := to_mem_id;
        xfr_rec.ord_no  := ord_num;
        xfr_rec.pr_id   := pr_num;
        xfr_rec.qty     := 0;
	-- fetch (create if necessary) the to_record for the product
        -- has to happen before we can make the xfer record
     	ml_to := open_mem_line(ord_num, to_mem_id, pr_rec, False, '');
        INSERT INTO xfer  (from_id, ord_no, to_id, pr_id, qty) VALUES
           (xfr_rec.from_id, xfr_rec.ord_no, xfr_rec.to_id,
            xfr_rec.pr_id, xfr_rec.qty);
     END IF;
     
     -- fetch (create if necessary) the to_record for the product
     ml_to := open_mem_line(ord_num, to_mem_id, pr_rec, False, '');

     IF ml_to.meml_xfer_out != 0 AND xfr_qty != 0 THEN
        RAISE EXCEPTION 'Can''t transfer items both to and from order for member %',
	  to_mem_id;
     END IF;

     -- delta is positive/negative if increasing/decreasing transfer amount
     delta                 := xfr_qty - xfr_rec.qty;
     ml_from.meml_pickup   := ml_from.meml_pickup   - delta;     
     ml_from.meml_xfer_out := ml_from.meml_xfer_out + delta;
     ml_to.meml_pickup     := ml_to.meml_pickup     + delta;
     ml_to.meml_xfer_in    := ml_to.meml_xfer_in    + delta;
     xfr_rec.qty           := xfr_qty;
     IF ml_from.meml_pickup < 0 THEN
        RAISE EXCEPTION 'Can''t transfer % items of product % from member %',
              xfr_qty, pr_num, from_mem_id;
     END IF;
     UPDATE mem_line SET meml_pickup = ml_from.meml_pickup, meml_xfer_out = 
        ml_from.meml_xfer_out WHERE mem_id = from_mem_id AND ord_no = ord_num
        AND pr_id = pr_num;

     -- we have to delete the xfer record when cancelling a transfer
     IF xfr_qty = 0 THEN
        DELETE FROM xfer WHERE from_id = from_mem_id AND to_id = to_mem_id
           AND pr_id = pr_num AND ord_no = ord_num;
     ELSE
        UPDATE xfer SET qty = xfr_qty WHERE from_id = from_mem_id AND 
	   to_id = to_mem_id AND pr_id = pr_num AND ord_no = ord_num;
     END IF;

     -- update recipitent
     UPDATE mem_line SET meml_pickup = ml_to.meml_pickup, meml_xfer_in =
         ml_to.meml_xfer_in WHERE mem_id = to_mem_id AND ord_no = ord_num
         AND pr_id = pr_num;
     RETURN;

END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.xfer_order(from_mem_id integer, to_mem_id integer, ord_num integer, pr_num integer, xfr_qty integer) OWNER TO jes;

--
-- Name: zap_interval(); Type: FUNCTION; Schema: public; Owner: jes
--

CREATE FUNCTION zap_interval(OUT newest timestamp with time zone, OUT penult timestamp with time zone) RETURNS record
    AS $$
   DECLARE
     zaptime CURSOR FOR 
                SELECT DISTINCT wh_last_seen 
                FROM zapatistadata ORDER BY wh_last_seen DESC LIMIT 2;
   BEGIN
     OPEN zaptime;
     FETCH zaptime INTO newest;
     FETCH zaptime INTO penult;
     CLOSE zaptime;
END;$$
    LANGUAGE plpgsql;


ALTER FUNCTION public.zap_interval(OUT newest timestamp with time zone, OUT penult timestamp with time zone) OWNER TO jes;

--
-- Name: mem_line; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE mem_line (
    ord_no integer,
    mem_id integer,
    pr_id integer,
    meml_qty integer NOT NULL,
    meml_adj integer NOT NULL,
    meml_rcv integer NOT NULL,
    meml_unit_price integer NOT NULL,
    meml_btw numeric NOT NULL,
    func_flag boolean DEFAULT false,
    meml_pickup integer DEFAULT 0,
    meml_ex_btw integer DEFAULT 0,
    meml_xfer_in integer DEFAULT 0,
    meml_xfer_out integer DEFAULT 0,
    meml_damaged integer DEFAULT 0,
    meml_missing integer DEFAULT 0,
    CONSTRAINT positive_madjt CHECK ((meml_adj >= 0)),
    CONSTRAINT positive_mqty CHECK ((meml_qty >= 0)),
    CONSTRAINT positive_mrcv CHECK (((meml_rcv >= 0) AND (meml_rcv <= meml_adj))),
    CONSTRAINT positive_pickup CHECK ((meml_pickup >= 0)),
    CONSTRAINT valid_pickup_shortage CHECK (((meml_damaged >= 0) AND (meml_missing >= 0))),
    CONSTRAINT valid_xfers CHECK ((((meml_xfer_in >= 0) AND (meml_xfer_out >= 0)) AND ((meml_xfer_in * meml_xfer_out) = 0)))
);


ALTER TABLE public.mem_line OWNER TO jes;

--
-- Name: members_mem_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE members_mem_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.members_mem_id_seq OWNER TO jes;

--
-- Name: members; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE members (
    mem_id integer DEFAULT nextval('members_mem_id_seq'::regclass) NOT NULL,
    mem_fname character varying NOT NULL,
    mem_prefix character varying DEFAULT ''::character varying NOT NULL,
    mem_lname character varying NOT NULL,
    mem_street character varying NOT NULL,
    mem_house integer NOT NULL,
    mem_flatno character varying DEFAULT ''::character varying NOT NULL,
    mem_city character varying DEFAULT 'Amsterdam'::character varying NOT NULL,
    mem_postcode character varying NOT NULL,
    mem_home_tel character varying DEFAULT ''::character varying NOT NULL,
    mem_mobile character varying DEFAULT ''::character varying NOT NULL,
    mem_email character varying NOT NULL,
    mem_enc_pwd character varying NOT NULL,
    mem_pwd_url character varying,
    mem_active boolean DEFAULT true,
    mem_cookie character varying,
    mem_ip character varying,
    mem_admin boolean DEFAULT false,
    mem_adm_adj boolean DEFAULT false,
    mem_work_tel character varying DEFAULT ''::character varying NOT NULL,
    mem_bank_no character varying DEFAULT ''::character varying NOT NULL,
    mem_adm_comment character varying DEFAULT ''::character varying NOT NULL,
    mem_message character varying DEFAULT ''::character varying NOT NULL,
    mem_news integer DEFAULT 0 NOT NULL,
    mem_message_auth integer,
    mem_message_date timestamp with time zone,
    mem_membership_paid boolean DEFAULT false,
    CONSTRAINT need_tel_no CHECK ((NOT ((((mem_home_tel)::text = ''::text) AND ((mem_mobile)::text = ''::text)) AND ((mem_work_tel)::text = ''::text)))),
    CONSTRAINT no_member_zero CHECK ((mem_id > 0))
);


ALTER TABLE public.members OWNER TO jes;

--
-- Name: order_header; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE order_header (
    mas_key integer DEFAULT 1 NOT NULL,
    ord_no integer NOT NULL,
    ord_label character varying NOT NULL,
    ord_status integer DEFAULT 0,
    oh_order_open timestamp with time zone,
    oh_commit_open timestamp with time zone,
    oh_commit_closed timestamp with time zone,
    oh_order_closed timestamp with time zone,
    oh_order_received timestamp with time zone,
    oh_order_completed timestamp with time zone,
    func_flag boolean DEFAULT false,
    CONSTRAINT one_order_header CHECK ((mas_key = 1))
);


ALTER TABLE public.order_header OWNER TO jes;

--
-- Name: adj_email; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW adj_email AS
    SELECT m.mem_email AS addr, ml.pr_id AS pr_no, pr.pr_desc, ml.meml_qty AS old_qty, ml.meml_adj AS new_qty FROM members m, mem_line ml, product pr, order_header oh WHERE ((((m.mem_active AND (m.mem_id = ml.mem_id)) AND (ml.ord_no = oh.ord_no)) AND (ml.pr_id = pr.pr_id)) AND (ml.meml_qty <> ml.meml_adj)) ORDER BY m.mem_email;


ALTER TABLE public.adj_email OWNER TO jes;

--
-- Name: carry_over; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE carry_over (
    mem_id integer NOT NULL,
    pr_id integer NOT NULL,
    qty integer NOT NULL,
    CONSTRAINT positive_carry_over_qty CHECK ((qty > 0))
);


ALTER TABLE public.carry_over OWNER TO jes;

--
-- Name: category_cat_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE category_cat_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.category_cat_id_seq OWNER TO jes;

--
-- Name: category; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE category (
    cat_id integer DEFAULT nextval('category_cat_id_seq'::regclass) NOT NULL,
    cat_name character varying NOT NULL,
    cat_desc character varying NOT NULL,
    cat_active boolean DEFAULT true
);


ALTER TABLE public.category OWNER TO jes;

--
-- Name: chg_email; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW chg_email AS
    SELECT m.mem_id AS m_id, ml.pr_id AS p_id FROM members m, mem_line ml, product pr, order_header oh WHERE ((((m.mem_active AND (m.mem_id = ml.mem_id)) AND (ml.ord_no = oh.ord_no)) AND (ml.pr_id = pr.pr_id)) AND pr.pr_changed);


ALTER TABLE public.chg_email OWNER TO jes;

--
-- Name: default_order; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE default_order (
    mem_id integer NOT NULL,
    pr_id integer NOT NULL,
    qty integer NOT NULL,
    CONSTRAINT positive_default_qty CHECK ((qty > 0))
);


ALTER TABLE public.default_order OWNER TO jes;

--
-- Name: dnbdata; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE dnbdata (
    wh_pr_id integer NOT NULL,
    wh_supplier character varying,
    wh_barcode character varying,
    wh_descr character varying NOT NULL,
    wh_brand character varying,
    wh_kwaliteit character varying,
    wh_size numeric,
    wh_wh_q integer NOT NULL,
    wh_unit character varying,
    wh_land character varying,
    wh_trefw character varying,
    wh_col_h integer,
    wh_col_g integer,
    wh_vol_s integer,
    wh_whpri integer NOT NULL,
    wh_btw numeric NOT NULL,
    wh_korting numeric,
    wh_statieg integer NOT NULL,
    wh_gluten boolean,
    wh_suiker boolean,
    wh_lactose boolean,
    wh_milk boolean,
    wh_salt boolean,
    wh_soya boolean,
    wh_yeast boolean,
    wh_veg boolean,
    is_product boolean DEFAULT true,
    is_changed boolean DEFAULT false,
    is_seen boolean DEFAULT false,
    is_skipped boolean DEFAULT false,
    wh_last_seen timestamp with time zone,
    wh_prev_seen timestamp with time zone,
    wh_prcode character varying DEFAULT ''::character varying
);


ALTER TABLE public.dnbdata OWNER TO jes;

--
-- Name: dnb_products; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW dnb_products AS
    SELECT w.wh_pr_id, w.wh_descr, w.wh_wh_q, w.wh_whpri, w.wh_btw, w.is_product, w.is_changed, w.is_seen, w.is_skipped, w.wh_prev_seen, w.wh_last_seen, p.pr_id, p.pr_cat, p.pr_sc, p.pr_wh_q, p.pr_margin, p.pr_mem_q, p.pr_wh_price, p.pr_active, p.pr_mq_chg, p.pr_btw, p.pr_mem_price, p.pr_desc, min_price(w.wh_whpri, w.wh_btw, p.pr_margin, w.wh_wh_q) AS rec_pr, min_price(w.wh_whpri, w.wh_btw, (1 + p.pr_margin), w.wh_wh_q) AS over_marg FROM (dnbdata w LEFT JOIN product p ON (((w.wh_prcode)::text = (p.wh_prcode)::text)));


ALTER TABLE public.dnb_products OWNER TO jes;

--
-- Name: dnb_view; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW dnb_view AS
    SELECT d.wh_pr_id, d.wh_prcode AS pr_code, 99999 AS pr_cat, d.wh_wh_q AS pr_wh_q, 5 AS pr_margin, 1 AS pr_mem_q, d.wh_whpri AS pr_wh_price, min_price(d.wh_whpri, d.wh_btw, 5, d.wh_wh_q) AS pr_mem_price, d.wh_descr AS pr_desc, d.wh_btw AS pr_btw, d.wh_last_seen, d.wh_prev_seen, d.is_seen, d.is_changed, d.is_skipped, d.is_product FROM dnbdata d;


ALTER TABLE public.dnb_view OWNER TO jes;

--
-- Name: edit_pr_view; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW edit_pr_view AS
    SELECT product.pr_id, product.pr_cat, product.pr_sc, product.pr_wh_q, product.pr_margin, product.pr_mem_q, product.pr_wh_price, product.pr_mem_price, product.pr_desc, product.pr_btw, product.pr_active FROM product ORDER BY product.pr_cat, product.pr_id;


ALTER TABLE public.edit_pr_view OWNER TO jes;

SET default_with_oids = false;

--
-- Name: email_changes; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE email_changes (
    mem_id integer NOT NULL,
    pr_id integer NOT NULL,
    meml_qty integer NOT NULL,
    meml_adj integer NOT NULL,
    meml_rcv integer NOT NULL,
    meml_unit_price integer NOT NULL,
    meml_btw numeric NOT NULL,
    notify_ty integer NOT NULL
);


ALTER TABLE public.email_changes OWNER TO jes;

--
-- Name: email_notices; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE email_notices (
    mem_id integer NOT NULL,
    notify_ty integer NOT NULL
);


ALTER TABLE public.email_notices OWNER TO jes;

--
-- Name: email_status_changes; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE email_status_changes (
    x integer
);


ALTER TABLE public.email_status_changes OWNER TO jes;

--
-- Name: mem_msg; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW mem_msg AS
    SELECT m.mem_id, m.mem_message AS body, to_char(m.mem_message_date, 'Dy DD Mon YYYY HH24:MI'::text) AS sent, join_name(a.mem_fname, a.mem_prefix, a.mem_lname) AS author FROM members m, members a WHERE (m.mem_message_auth = a.mem_id);


ALTER TABLE public.mem_msg OWNER TO jes;

--
-- Name: mem_names_current_order; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW mem_names_current_order AS
    SELECT members.mem_id, join_name(members.mem_fname, members.mem_prefix, members.mem_lname) AS mem_name FROM members WHERE (members.mem_id IN (SELECT DISTINCT ml.mem_id FROM mem_line ml WHERE (ml.ord_no IN (SELECT order_header.ord_no FROM order_header)) ORDER BY ml.mem_id));


ALTER TABLE public.mem_names_current_order OWNER TO jes;

SET default_with_oids = true;

--
-- Name: mem_order; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE mem_order (
    ord_no integer NOT NULL,
    mem_id integer NOT NULL,
    memo_order_open timestamp with time zone,
    memo_commit_open timestamp with time zone,
    memo_commit_closed timestamp with time zone,
    memo_closed timestamp with time zone,
    memo_order_received timestamp with time zone,
    memo_completed timestamp with time zone,
    memo_amt integer NOT NULL,
    func_flag boolean DEFAULT false,
    ord_label character varying,
    mo_stgeld_rxed integer DEFAULT 0,
    mo_stgeld_refunded integer DEFAULT 0,
    mo_crates_rxed integer DEFAULT 0,
    mo_crates_refunded integer DEFAULT 0,
    mo_misc_rxed integer DEFAULT 0,
    mo_misc_refunded integer DEFAULT 0,
    mo_checked_out boolean DEFAULT false,
    mo_checked_out_by integer,
    mo_membership integer DEFAULT 0
);


ALTER TABLE public.mem_order OWNER TO jes;

--
-- Name: member_news_news_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE member_news_news_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.member_news_news_id_seq OWNER TO jes;

--
-- Name: member_news; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE member_news (
    news_id integer DEFAULT nextval('member_news_news_id_seq'::regclass) NOT NULL,
    news_auth integer,
    news_date timestamp with time zone,
    news_text character varying DEFAULT ''::character varying NOT NULL,
    news_mod_date timestamp with time zone,
    news_mod_auth integer
);


ALTER TABLE public.member_news OWNER TO jes;

--
-- Name: wh_line; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE wh_line (
    ord_no integer NOT NULL,
    wh_id integer NOT NULL,
    pr_id integer NOT NULL,
    whl_qty integer NOT NULL,
    whl_rcv integer NOT NULL,
    wh_prcode character varying NOT NULL,
    whl_price integer NOT NULL,
    whl_btw numeric NOT NULL,
    whl_mem_qty integer NOT NULL,
    CONSTRAINT postive_mem_qty CHECK ((whl_mem_qty >= 0)),
    CONSTRAINT postive_qty CHECK ((whl_qty >= 0)),
    CONSTRAINT postive_rcv_qty CHECK ((whl_rcv >= 0))
);


ALTER TABLE public.wh_line OWNER TO jes;

--
-- Name: mo_view; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW mo_view AS
    SELECT mem.mem_id, pr.pr_cat AS cat_id, pr.pr_sc AS sc_id, ml.ord_no, pr.pr_id, wl.wh_id AS wh_no, pr.wh_prcode AS wh_prodno, pr.pr_desc AS descr, wl.whl_mem_qty AS all_orders, short((pr.pr_wh_q * wl.whl_qty), wl.whl_mem_qty, pr.pr_wh_q) AS shortage, (((ml.meml_unit_price)::numeric / 100.0))::numeric(10,2) AS price, ml.meml_rcv AS qty, (((ml.meml_rcv * ml.meml_unit_price) / 100))::numeric(10,2) AS cost FROM members mem, product pr, wh_line wl, mem_line ml, order_header oh WHERE (((((mem.mem_id = ml.mem_id) AND (ml.pr_id = pr.pr_id)) AND (ml.pr_id = wl.pr_id)) AND (ml.ord_no = wl.ord_no)) AND (oh.ord_no = wl.ord_no)) ORDER BY ml.pr_id;


ALTER TABLE public.mo_view OWNER TO jes;

--
-- Name: mo_view_all; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW mo_view_all AS
    SELECT ml.ord_no, mem.mem_id, pr.pr_cat AS cat_id, pr.pr_sc AS sc_id, pr.pr_id, pr.pr_desc AS descr, wl.wh_id AS wh_no, pr.wh_prcode AS wh_prodno, wl.whl_mem_qty AS all_orders, short((pr.pr_wh_q * wl.whl_qty), wl.whl_mem_qty, pr.pr_wh_q) AS shortage, (((ml.meml_unit_price)::numeric / 100.0))::numeric(10,2) AS price, ml.meml_rcv AS qty, (((ml.meml_rcv * ml.meml_unit_price) / 100))::numeric(10,2) AS cost FROM members mem, product pr, wh_line wl, mem_line ml WHERE ((((mem.mem_id = ml.mem_id) AND (ml.pr_id = pr.pr_id)) AND (ml.pr_id = wl.pr_id)) AND (ml.ord_no = wl.ord_no)) ORDER BY ml.ord_no DESC, ml.pr_id;


ALTER TABLE public.mo_view_all OWNER TO jes;

--
-- Name: news; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW news AS
    SELECT n.news_id, n.news_text AS body, to_char(n.news_date, 'Dy DD Mon YYYY HH24:MI'::text) AS posted, join_name(a.mem_fname, a.mem_prefix, a.mem_lname) AS author, to_char(n.news_mod_date, 'Dy DD Mon YYYY HH24:MI'::text) AS modified, join_name(u.mem_fname, u.mem_prefix, u.mem_lname) AS updater FROM member_news n, members a, members u WHERE ((n.news_auth = a.mem_id) AND (n.news_mod_auth = u.mem_id)) ORDER BY n.news_id DESC;


ALTER TABLE public.news OWNER TO jes;

SET default_with_oids = false;

--
-- Name: order_notes; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE order_notes (
    ord_no integer NOT NULL,
    mem_id integer NOT NULL,
    note character varying DEFAULT ''::character varying
);


ALTER TABLE public.order_notes OWNER TO jes;

--
-- Name: product_changes; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE product_changes (
    pr_id integer NOT NULL,
    pr_mem_q integer NOT NULL,
    pr_mem_price integer NOT NULL,
    pr_wh_q integer NOT NULL,
    pr_wh_price integer NOT NULL,
    pr_btw numeric NOT NULL,
    pr_active boolean NOT NULL,
    pr_changed timestamp with time zone NOT NULL
);


ALTER TABLE public.product_changes OWNER TO jes;

--
-- Name: rcv_email; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW rcv_email AS
    SELECT m.mem_email AS addr, ml.pr_id AS pr_no, pr.pr_desc, ml.meml_adj AS old_qty, ml.meml_rcv AS new_qty FROM members m, mem_line ml, product pr, order_header oh WHERE ((((m.mem_active AND (m.mem_id = ml.mem_id)) AND (ml.ord_no = oh.ord_no)) AND (ml.pr_id = pr.pr_id)) AND (ml.meml_rcv <> ml.meml_adj)) ORDER BY m.mem_email;


ALTER TABLE public.rcv_email OWNER TO jes;

--
-- Name: sh_email; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW sh_email AS
    SELECT m.mem_email AS addr FROM members m, mem_order mo, order_header oh WHERE ((m.mem_active AND (m.mem_id = mo.mem_id)) AND (oh.ord_no = mo.ord_no)) ORDER BY m.mem_id;


ALTER TABLE public.sh_email OWNER TO jes;

--
-- Name: sh_view; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW sh_view AS
    SELECT ml.ord_no, mem.mem_id, pr.pr_cat AS cat_id, pr.pr_sc AS sc_id, pr.pr_id, wl.wh_id AS wh_no, pr.wh_prcode AS wh_prodno, pr.pr_wh_q AS wh_q, pr.pr_desc AS descr, wl.whl_mem_qty AS mem_qty, ml.meml_qty AS ordered, ml.meml_adj AS adjusted, ml.meml_rcv AS qty, wl.whl_qty AS wh_ord, wl.whl_rcv AS wh_rcv, (wl.whl_mem_qty - (pr.pr_wh_q * wl.whl_rcv)) AS reduce_by, ((floor((pr.pr_mem_price)::double precision) / (100)::double precision))::numeric(10,2) AS unit_pr, ((floor(((ml.meml_rcv * pr.pr_mem_price))::double precision) / (100)::double precision))::numeric(10,2) AS cost FROM members mem, product pr, wh_line wl, mem_line ml, order_header oh WHERE ((((((mem.mem_id = ml.mem_id) AND (ml.pr_id = pr.pr_id)) AND (ml.pr_id = wl.pr_id)) AND (ml.ord_no = wl.ord_no)) AND (oh.ord_no = ml.ord_no)) AND ((wl.whl_mem_qty <> (wl.whl_rcv * pr.pr_wh_q)) OR (ml.meml_qty <> ml.meml_rcv))) ORDER BY pr.pr_id, ml.meml_rcv DESC;


ALTER TABLE public.sh_view OWNER TO jes;

--
-- Name: sub_cat_sc_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE sub_cat_sc_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.sub_cat_sc_id_seq OWNER TO jes;

SET default_with_oids = true;

--
-- Name: sub_cat; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE sub_cat (
    sc_id integer DEFAULT nextval('sub_cat_sc_id_seq'::regclass) NOT NULL,
    cat_id integer NOT NULL,
    sc_name character varying NOT NULL,
    sc_desc character varying NOT NULL,
    sc_active boolean DEFAULT true
);


ALTER TABLE public.sub_cat OWNER TO jes;

--
-- Name: unc_email; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW unc_email AS
    SELECT m.mem_id, m.mem_email, join_name(m.mem_fname, m.mem_prefix, m.mem_lname) AS fullname FROM members m, mem_order mo, order_header oh WHERE (((m.mem_active AND (m.mem_id = mo.mem_id)) AND (mo.memo_commit_closed IS NULL)) AND (oh.ord_no = mo.ord_no)) ORDER BY m.mem_id;


ALTER TABLE public.unc_email OWNER TO jes;

--
-- Name: wh_order; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE wh_order (
    ord_no integer NOT NULL,
    wh_id integer NOT NULL,
    who_order_open timestamp with time zone,
    who_commit_open timestamp with time zone,
    who_commit_closed timestamp with time zone,
    who_order_closed timestamp with time zone,
    who_order_received timestamp with time zone,
    who_order_completed timestamp with time zone,
    who_amt_ex_btw integer NOT NULL,
    who_amt_btw numeric NOT NULL,
    func_flag boolean DEFAULT false,
    ord_label character varying
);


ALTER TABLE public.wh_order OWNER TO jes;

--
-- Name: wh_view; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW wh_view AS
    SELECT wl.wh_id AS wh_no, wl.pr_id, wl.wh_prcode AS prcode, pr.wh_desc AS descr, wl.whl_qty AS qty, wl.whl_rcv AS received, ((((wl.whl_price * wl.whl_rcv))::numeric / 100.0))::numeric(10,2) AS price, ((((((wl.whl_price * wl.whl_rcv))::numeric * ((100)::numeric + wl.whl_btw)) / 100.0) / 100.0))::numeric(10,2) AS price_inc_btw FROM product pr, wh_line wl, order_header oh WHERE ((wl.pr_id = pr.pr_id) AND (oh.ord_no = wl.ord_no)) ORDER BY wl.ord_no, wl.wh_id, pr.pr_id;


ALTER TABLE public.wh_view OWNER TO jes;

--
-- Name: wh_view_all; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW wh_view_all AS
    SELECT wl.wh_id AS wh_no, wl.ord_no, wl.wh_prcode AS prcode, pr.wh_desc AS descr, wl.pr_id, wl.whl_qty AS qty, wl.whl_rcv AS received, ((((wl.whl_price * wl.whl_rcv))::numeric / 100.0))::numeric(10,2) AS price, ((((((wl.whl_price * wl.whl_rcv))::numeric * ((100)::numeric + wl.whl_btw)) / 100.0) / 100.0))::numeric(10,2) AS price_inc_btw FROM product pr, wh_line wl WHERE (wl.pr_id = pr.pr_id) ORDER BY wl.ord_no DESC, wl.wh_id, pr.pr_id;


ALTER TABLE public.wh_view_all OWNER TO jes;

--
-- Name: wholesaler_wh_id_seq; Type: SEQUENCE; Schema: public; Owner: jes
--

CREATE SEQUENCE wholesaler_wh_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.wholesaler_wh_id_seq OWNER TO jes;

--
-- Name: wholesaler; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE wholesaler (
    wh_id integer DEFAULT nextval('wholesaler_wh_id_seq'::regclass) NOT NULL,
    wh_name character varying NOT NULL,
    wh_addr1 character varying NOT NULL,
    wh_addr2 character varying DEFAULT ''::character varying NOT NULL,
    wh_addr3 character varying DEFAULT ''::character varying NOT NULL,
    wh_city character varying DEFAULT 'Amsterdam'::character varying NOT NULL,
    wh_postcode character varying NOT NULL,
    wh_tel character varying DEFAULT ''::character varying NOT NULL,
    wh_fax character varying DEFAULT ''::character varying NOT NULL,
    wh_active boolean DEFAULT true,
    wh_update character varying DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.wholesaler OWNER TO jes;

SET default_with_oids = false;

--
-- Name: xfer; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE xfer (
    from_id integer NOT NULL,
    ord_no integer NOT NULL,
    to_id integer NOT NULL,
    pr_id integer NOT NULL,
    qty integer NOT NULL,
    CONSTRAINT valid_xfer_qty CHECK ((qty >= 0))
);


ALTER TABLE public.xfer OWNER TO jes;

--
-- Name: zapatistadata; Type: TABLE; Schema: public; Owner: jes; Tablespace: 
--

CREATE TABLE zapatistadata (
    wh_pr_id integer NOT NULL,
    wh_whpri integer NOT NULL,
    wh_btw numeric NOT NULL,
    wh_descr character varying NOT NULL,
    wh_url character varying DEFAULT ''::character varying,
    wh_wh_q integer NOT NULL,
    is_product boolean DEFAULT true,
    is_changed boolean DEFAULT false,
    is_seen boolean DEFAULT false,
    is_skipped boolean DEFAULT false,
    wh_last_seen timestamp with time zone,
    wh_prev_seen timestamp with time zone,
    wh_prcode character varying DEFAULT ''::character varying,
    CONSTRAINT zap_btw_valid CHECK ((((wh_btw = (0)::numeric) OR (wh_btw = (6)::numeric)) OR (wh_btw = (19)::numeric)))
);


ALTER TABLE public.zapatistadata OWNER TO jes;

--
-- Name: zap_products; Type: VIEW; Schema: public; Owner: jes
--

CREATE VIEW zap_products AS
    SELECT w.wh_pr_id, w.wh_descr, w.wh_wh_q, w.wh_whpri, w.wh_btw, w.is_product, w.is_changed, w.is_seen, w.is_skipped, w.wh_prev_seen, w.wh_last_seen, p.pr_id, p.pr_cat, p.pr_sc, p.pr_wh_q, p.pr_margin, p.pr_mem_q, p.pr_wh_price, p.pr_active, p.pr_mq_chg, p.pr_btw, p.pr_mem_price, p.pr_desc, min_price(w.wh_whpri, w.wh_btw, p.pr_margin, w.wh_wh_q) AS rec_pr, min_price(w.wh_whpri, w.wh_btw, (1 + p.pr_margin), w.wh_wh_q) AS over_marg FROM (zapatistadata w LEFT JOIN product p ON (((w.wh_prcode)::text = (p.wh_prcode)::text)));


ALTER TABLE public.zap_products OWNER TO jes;

--
-- Name: carry_over_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY carry_over
    ADD CONSTRAINT carry_over_pkey PRIMARY KEY (mem_id, pr_id);


--
-- Name: category_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY category
    ADD CONSTRAINT category_pkey PRIMARY KEY (cat_id);


--
-- Name: default_order_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY default_order
    ADD CONSTRAINT default_order_pkey PRIMARY KEY (mem_id, pr_id);


--
-- Name: dnbdata_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY dnbdata
    ADD CONSTRAINT dnbdata_pkey PRIMARY KEY (wh_pr_id);


--
-- Name: mem_line_mem_id_key; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY mem_line
    ADD CONSTRAINT mem_line_mem_id_key UNIQUE (mem_id, ord_no, pr_id);


--
-- Name: mem_order_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY mem_order
    ADD CONSTRAINT mem_order_pkey PRIMARY KEY (ord_no, mem_id);


--
-- Name: member_news_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY member_news
    ADD CONSTRAINT member_news_pkey PRIMARY KEY (news_id);


--
-- Name: members_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY members
    ADD CONSTRAINT members_pkey PRIMARY KEY (mem_id);


--
-- Name: order_header_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY order_header
    ADD CONSTRAINT order_header_pkey PRIMARY KEY (mas_key);


--
-- Name: product_changes_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY product_changes
    ADD CONSTRAINT product_changes_pkey PRIMARY KEY (pr_id, pr_changed);


--
-- Name: product_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY product
    ADD CONSTRAINT product_pkey PRIMARY KEY (pr_id);


--
-- Name: sub_cat_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY sub_cat
    ADD CONSTRAINT sub_cat_pkey PRIMARY KEY (cat_id, sc_id);


--
-- Name: wh_line_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY wh_line
    ADD CONSTRAINT wh_line_pkey PRIMARY KEY (ord_no, wh_id, pr_id);


--
-- Name: wh_order_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY wh_order
    ADD CONSTRAINT wh_order_pkey PRIMARY KEY (ord_no, wh_id);


--
-- Name: wholesaler_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY wholesaler
    ADD CONSTRAINT wholesaler_pkey PRIMARY KEY (wh_id);


--
-- Name: zapatistadata_pkey; Type: CONSTRAINT; Schema: public; Owner: jes; Tablespace: 
--

ALTER TABLE ONLY zapatistadata
    ADD CONSTRAINT zapatistadata_pkey PRIMARY KEY (wh_pr_id);


--
-- Name: idx_cat_name; Type: INDEX; Schema: public; Owner: jes; Tablespace: 
--

CREATE UNIQUE INDEX idx_cat_name ON category USING btree (cat_name);


--
-- Name: idx_mem_email; Type: INDEX; Schema: public; Owner: jes; Tablespace: 
--

CREATE UNIQUE INDEX idx_mem_email ON members USING btree (mem_email);


--
-- Name: idx_ord_label; Type: INDEX; Schema: public; Owner: jes; Tablespace: 
--

CREATE UNIQUE INDEX idx_ord_label ON order_header USING btree (ord_label);


--
-- Name: idx_sc_name; Type: INDEX; Schema: public; Owner: jes; Tablespace: 
--

CREATE UNIQUE INDEX idx_sc_name ON sub_cat USING btree (cat_id, sc_name);


--
-- Name: idx_wh_prcode; Type: INDEX; Schema: public; Owner: jes; Tablespace: 
--

CREATE UNIQUE INDEX idx_wh_prcode ON product USING btree (pr_wh, wh_prcode);


--
-- Name: init_product; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER init_product
    BEFORE INSERT ON product
    FOR EACH ROW
    EXECUTE PROCEDURE set_member_price();


--
-- Name: message_update; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER message_update
    BEFORE UPDATE ON members
    FOR EACH ROW
    EXECUTE PROCEDURE message_update();


--
-- Name: news_insert; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER news_insert
    BEFORE INSERT ON member_news
    FOR EACH ROW
    EXECUTE PROCEDURE news_insert();


--
-- Name: news_update; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER news_update
    BEFORE UPDATE ON member_news
    FOR EACH ROW
    EXECUTE PROCEDURE news_update();


--
-- Name: oh_change_status; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER oh_change_status
    AFTER UPDATE ON order_header
    FOR EACH ROW
    EXECUTE PROCEDURE status_change();


--
-- Name: oh_insert; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER oh_insert
    BEFORE INSERT ON order_header
    FOR EACH ROW
    EXECUTE PROCEDURE first_insert();


--
-- Name: product_update; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER product_update
    BEFORE UPDATE ON product
    FOR EACH ROW
    EXECUTE PROCEDURE update_member_price();


--
-- Name: unique_mem_adm_adj; Type: TRIGGER; Schema: public; Owner: jes
--

CREATE TRIGGER unique_mem_adm_adj
    AFTER INSERT OR UPDATE ON members
    FOR EACH ROW
    EXECUTE PROCEDURE check_unique_adm_adj();


--
-- Name: carry_over_mem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY carry_over
    ADD CONSTRAINT carry_over_mem_id_fkey FOREIGN KEY (mem_id) REFERENCES members(mem_id);


--
-- Name: carry_over_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY carry_over
    ADD CONSTRAINT carry_over_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: default_order_mem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY default_order
    ADD CONSTRAINT default_order_mem_id_fkey FOREIGN KEY (mem_id) REFERENCES members(mem_id);


--
-- Name: default_order_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY default_order
    ADD CONSTRAINT default_order_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: email_changes_mem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY email_changes
    ADD CONSTRAINT email_changes_mem_id_fkey FOREIGN KEY (mem_id) REFERENCES members(mem_id);


--
-- Name: email_changes_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY email_changes
    ADD CONSTRAINT email_changes_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: email_notices_mem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY email_notices
    ADD CONSTRAINT email_notices_mem_id_fkey FOREIGN KEY (mem_id) REFERENCES members(mem_id);


--
-- Name: mem_line_ord_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY mem_line
    ADD CONSTRAINT mem_line_ord_no_fkey FOREIGN KEY (ord_no, mem_id) REFERENCES mem_order(ord_no, mem_id);


--
-- Name: mem_line_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY mem_line
    ADD CONSTRAINT mem_line_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: member_news_news_auth_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY member_news
    ADD CONSTRAINT member_news_news_auth_fkey FOREIGN KEY (news_auth) REFERENCES members(mem_id);


--
-- Name: member_news_news_mod_auth_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY member_news
    ADD CONSTRAINT member_news_news_mod_auth_fkey FOREIGN KEY (news_mod_auth) REFERENCES members(mem_id);


--
-- Name: members_mem_message_auth_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY members
    ADD CONSTRAINT members_mem_message_auth_fkey FOREIGN KEY (mem_message_auth) REFERENCES members(mem_id);


--
-- Name: order_notes_ord_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY order_notes
    ADD CONSTRAINT order_notes_ord_no_fkey FOREIGN KEY (ord_no, mem_id) REFERENCES mem_order(ord_no, mem_id);


--
-- Name: product_changes_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY product_changes
    ADD CONSTRAINT product_changes_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: product_pr_sc_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY product
    ADD CONSTRAINT product_pr_sc_fkey FOREIGN KEY (pr_sc, pr_cat) REFERENCES sub_cat(sc_id, cat_id);


--
-- Name: product_pr_wh_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY product
    ADD CONSTRAINT product_pr_wh_fkey FOREIGN KEY (pr_wh) REFERENCES wholesaler(wh_id);


--
-- Name: sub_cat_cat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY sub_cat
    ADD CONSTRAINT sub_cat_cat_id_fkey FOREIGN KEY (cat_id) REFERENCES category(cat_id);


--
-- Name: wh_line_ord_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY wh_line
    ADD CONSTRAINT wh_line_ord_no_fkey FOREIGN KEY (ord_no, wh_id) REFERENCES wh_order(ord_no, wh_id);


--
-- Name: wh_line_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY wh_line
    ADD CONSTRAINT wh_line_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES product(pr_id);


--
-- Name: wh_line_wh_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY wh_line
    ADD CONSTRAINT wh_line_wh_id_fkey FOREIGN KEY (wh_id, wh_prcode) REFERENCES product(pr_wh, wh_prcode);


--
-- Name: xfer_from_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY xfer
    ADD CONSTRAINT xfer_from_id_fkey FOREIGN KEY (from_id, ord_no, pr_id) REFERENCES mem_line(mem_id, ord_no, pr_id);


--
-- Name: xfer_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: jes
--

ALTER TABLE ONLY xfer
    ADD CONSTRAINT xfer_to_id_fkey FOREIGN KEY (to_id, ord_no, pr_id) REFERENCES mem_line(mem_id, ord_no, pr_id);


--
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: product_pr_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE product_pr_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE product_pr_id_seq FROM jes;
GRANT ALL ON TABLE product_pr_id_seq TO jes;
GRANT ALL ON TABLE product_pr_id_seq TO apache;


--
-- Name: product; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE product FROM PUBLIC;
REVOKE ALL ON TABLE product FROM jes;
GRANT ALL ON TABLE product TO jes;
GRANT ALL ON TABLE product TO apache;


--
-- Name: mem_line; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mem_line FROM PUBLIC;
REVOKE ALL ON TABLE mem_line FROM jes;
GRANT ALL ON TABLE mem_line TO jes;
GRANT ALL ON TABLE mem_line TO apache;


--
-- Name: members_mem_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE members_mem_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE members_mem_id_seq FROM jes;
GRANT ALL ON TABLE members_mem_id_seq TO jes;
GRANT ALL ON TABLE members_mem_id_seq TO apache;


--
-- Name: members; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE members FROM PUBLIC;
REVOKE ALL ON TABLE members FROM jes;
GRANT ALL ON TABLE members TO jes;
GRANT ALL ON TABLE members TO apache;


--
-- Name: order_header; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE order_header FROM PUBLIC;
REVOKE ALL ON TABLE order_header FROM jes;
GRANT ALL ON TABLE order_header TO jes;
GRANT ALL ON TABLE order_header TO apache;


--
-- Name: adj_email; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE adj_email FROM PUBLIC;
REVOKE ALL ON TABLE adj_email FROM jes;
GRANT ALL ON TABLE adj_email TO jes;
GRANT ALL ON TABLE adj_email TO apache;


--
-- Name: carry_over; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE carry_over FROM PUBLIC;
REVOKE ALL ON TABLE carry_over FROM jes;
GRANT ALL ON TABLE carry_over TO jes;
GRANT ALL ON TABLE carry_over TO apache;


--
-- Name: category_cat_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE category_cat_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE category_cat_id_seq FROM jes;
GRANT ALL ON TABLE category_cat_id_seq TO jes;
GRANT ALL ON TABLE category_cat_id_seq TO apache;


--
-- Name: category; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE category FROM PUBLIC;
REVOKE ALL ON TABLE category FROM jes;
GRANT ALL ON TABLE category TO jes;
GRANT ALL ON TABLE category TO apache;


--
-- Name: chg_email; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE chg_email FROM PUBLIC;
REVOKE ALL ON TABLE chg_email FROM jes;
GRANT ALL ON TABLE chg_email TO jes;
GRANT ALL ON TABLE chg_email TO apache;


--
-- Name: default_order; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE default_order FROM PUBLIC;
REVOKE ALL ON TABLE default_order FROM jes;
GRANT ALL ON TABLE default_order TO jes;
GRANT ALL ON TABLE default_order TO apache;


--
-- Name: dnbdata; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE dnbdata FROM PUBLIC;
REVOKE ALL ON TABLE dnbdata FROM jes;
GRANT ALL ON TABLE dnbdata TO jes;
GRANT ALL ON TABLE dnbdata TO apache;


--
-- Name: dnb_products; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE dnb_products FROM PUBLIC;
REVOKE ALL ON TABLE dnb_products FROM jes;
GRANT ALL ON TABLE dnb_products TO jes;
GRANT ALL ON TABLE dnb_products TO apache;


--
-- Name: dnb_view; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE dnb_view FROM PUBLIC;
REVOKE ALL ON TABLE dnb_view FROM jes;
GRANT ALL ON TABLE dnb_view TO jes;
GRANT ALL ON TABLE dnb_view TO apache;


--
-- Name: edit_pr_view; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE edit_pr_view FROM PUBLIC;
REVOKE ALL ON TABLE edit_pr_view FROM jes;
GRANT ALL ON TABLE edit_pr_view TO jes;
GRANT ALL ON TABLE edit_pr_view TO apache;


--
-- Name: email_changes; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE email_changes FROM PUBLIC;
REVOKE ALL ON TABLE email_changes FROM jes;
GRANT ALL ON TABLE email_changes TO jes;
GRANT ALL ON TABLE email_changes TO apache;


--
-- Name: email_notices; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE email_notices FROM PUBLIC;
REVOKE ALL ON TABLE email_notices FROM jes;
GRANT ALL ON TABLE email_notices TO jes;
GRANT ALL ON TABLE email_notices TO apache;


--
-- Name: email_status_changes; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE email_status_changes FROM PUBLIC;
REVOKE ALL ON TABLE email_status_changes FROM jes;
GRANT ALL ON TABLE email_status_changes TO jes;
GRANT ALL ON TABLE email_status_changes TO apache;


--
-- Name: mem_msg; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mem_msg FROM PUBLIC;
REVOKE ALL ON TABLE mem_msg FROM jes;
GRANT ALL ON TABLE mem_msg TO jes;
GRANT ALL ON TABLE mem_msg TO apache;


--
-- Name: mem_names_current_order; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mem_names_current_order FROM PUBLIC;
REVOKE ALL ON TABLE mem_names_current_order FROM jes;
GRANT ALL ON TABLE mem_names_current_order TO jes;
GRANT ALL ON TABLE mem_names_current_order TO apache;


--
-- Name: mem_order; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mem_order FROM PUBLIC;
REVOKE ALL ON TABLE mem_order FROM jes;
GRANT ALL ON TABLE mem_order TO jes;
GRANT ALL ON TABLE mem_order TO apache;


--
-- Name: member_news_news_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE member_news_news_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE member_news_news_id_seq FROM jes;
GRANT ALL ON TABLE member_news_news_id_seq TO jes;
GRANT ALL ON TABLE member_news_news_id_seq TO apache;


--
-- Name: member_news; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE member_news FROM PUBLIC;
REVOKE ALL ON TABLE member_news FROM jes;
GRANT ALL ON TABLE member_news TO jes;
GRANT ALL ON TABLE member_news TO apache;


--
-- Name: wh_line; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wh_line FROM PUBLIC;
REVOKE ALL ON TABLE wh_line FROM jes;
GRANT ALL ON TABLE wh_line TO jes;
GRANT ALL ON TABLE wh_line TO apache;


--
-- Name: mo_view; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mo_view FROM PUBLIC;
REVOKE ALL ON TABLE mo_view FROM jes;
GRANT ALL ON TABLE mo_view TO jes;
GRANT ALL ON TABLE mo_view TO apache;


--
-- Name: mo_view_all; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE mo_view_all FROM PUBLIC;
REVOKE ALL ON TABLE mo_view_all FROM jes;
GRANT ALL ON TABLE mo_view_all TO jes;
GRANT ALL ON TABLE mo_view_all TO apache;


--
-- Name: news; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE news FROM PUBLIC;
REVOKE ALL ON TABLE news FROM jes;
GRANT ALL ON TABLE news TO jes;
GRANT ALL ON TABLE news TO apache;


--
-- Name: order_notes; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE order_notes FROM PUBLIC;
REVOKE ALL ON TABLE order_notes FROM jes;
GRANT ALL ON TABLE order_notes TO jes;
GRANT ALL ON TABLE order_notes TO apache;


--
-- Name: product_changes; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE product_changes FROM PUBLIC;
REVOKE ALL ON TABLE product_changes FROM jes;
GRANT ALL ON TABLE product_changes TO jes;
GRANT ALL ON TABLE product_changes TO apache;


--
-- Name: rcv_email; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE rcv_email FROM PUBLIC;
REVOKE ALL ON TABLE rcv_email FROM jes;
GRANT ALL ON TABLE rcv_email TO jes;
GRANT ALL ON TABLE rcv_email TO apache;


--
-- Name: sh_email; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE sh_email FROM PUBLIC;
REVOKE ALL ON TABLE sh_email FROM jes;
GRANT ALL ON TABLE sh_email TO jes;
GRANT ALL ON TABLE sh_email TO apache;


--
-- Name: sh_view; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE sh_view FROM PUBLIC;
REVOKE ALL ON TABLE sh_view FROM jes;
GRANT ALL ON TABLE sh_view TO jes;
GRANT ALL ON TABLE sh_view TO apache;


--
-- Name: sub_cat_sc_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE sub_cat_sc_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE sub_cat_sc_id_seq FROM jes;
GRANT ALL ON TABLE sub_cat_sc_id_seq TO jes;
GRANT ALL ON TABLE sub_cat_sc_id_seq TO apache;


--
-- Name: sub_cat; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE sub_cat FROM PUBLIC;
REVOKE ALL ON TABLE sub_cat FROM jes;
GRANT ALL ON TABLE sub_cat TO jes;
GRANT ALL ON TABLE sub_cat TO apache;


--
-- Name: unc_email; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE unc_email FROM PUBLIC;
REVOKE ALL ON TABLE unc_email FROM jes;
GRANT ALL ON TABLE unc_email TO jes;
GRANT ALL ON TABLE unc_email TO apache;


--
-- Name: wh_order; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wh_order FROM PUBLIC;
REVOKE ALL ON TABLE wh_order FROM jes;
GRANT ALL ON TABLE wh_order TO jes;
GRANT ALL ON TABLE wh_order TO apache;


--
-- Name: wh_view; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wh_view FROM PUBLIC;
REVOKE ALL ON TABLE wh_view FROM jes;
GRANT ALL ON TABLE wh_view TO jes;
GRANT ALL ON TABLE wh_view TO apache;


--
-- Name: wh_view_all; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wh_view_all FROM PUBLIC;
REVOKE ALL ON TABLE wh_view_all FROM jes;
GRANT ALL ON TABLE wh_view_all TO jes;
GRANT ALL ON TABLE wh_view_all TO apache;


--
-- Name: wholesaler_wh_id_seq; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wholesaler_wh_id_seq FROM PUBLIC;
REVOKE ALL ON TABLE wholesaler_wh_id_seq FROM jes;
GRANT ALL ON TABLE wholesaler_wh_id_seq TO jes;
GRANT ALL ON TABLE wholesaler_wh_id_seq TO apache;


--
-- Name: wholesaler; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE wholesaler FROM PUBLIC;
REVOKE ALL ON TABLE wholesaler FROM jes;
GRANT ALL ON TABLE wholesaler TO jes;
GRANT ALL ON TABLE wholesaler TO apache;


--
-- Name: xfer; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE xfer FROM PUBLIC;
REVOKE ALL ON TABLE xfer FROM jes;
GRANT ALL ON TABLE xfer TO jes;
GRANT ALL ON TABLE xfer TO apache;


--
-- Name: zapatistadata; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE zapatistadata FROM PUBLIC;
REVOKE ALL ON TABLE zapatistadata FROM jes;
GRANT ALL ON TABLE zapatistadata TO jes;
GRANT ALL ON TABLE zapatistadata TO apache;


--
-- Name: zap_products; Type: ACL; Schema: public; Owner: jes
--

REVOKE ALL ON TABLE zap_products FROM PUBLIC;
REVOKE ALL ON TABLE zap_products FROM jes;
GRANT ALL ON TABLE zap_products TO jes;
GRANT ALL ON TABLE zap_products TO apache;


--
-- PostgreSQL database dump complete
--

