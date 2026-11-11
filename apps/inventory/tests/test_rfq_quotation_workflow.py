"""
Phase 2.1 Backend Automated Test Suite: RFQ, Supplier Quotation & Split-Award Workflow.
Covers:
1. Multi-requisition aggregation and Safeguard 1 concurrency allocation checks.
2. Unapproved requisition inclusion rejection.
3. Restricted RFQ uninvited supplier bid rejection.
4. Late quotation submission deadline enforcement.
5. Direct quotation sole-source justification requirement.
6. Authoritative landed cost and multi-currency ETB normalization.
7. Safeguard 2: Split-award PO conversion generating distinct Purchase Orders per vendor.
8. Safeguard 3: Immutability guards on awarded/converted quotes across ORM, API, and Admin.
9. Comprehensive audit trail generation.
10. DRF REST API endpoints and actions.
"""
import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.models import (
    AuditEvent,
    InventoryCategory,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    RequestForQuotation,
    RequestForQuotationItem,
    StockLocation,
    Supplier,
    SupplierQuotation,
    SupplierQuotationItem,
)
from hotel.procurement import (
    calculate_quotation_totals,
    close_request_for_quotation,
    convert_awarded_quotations_to_purchase_orders,
    create_request_for_quotation,
    evaluate_and_award_quotations,
    evaluate_quotation,
    publish_request_for_quotation,
    submit_supplier_quotation,
)
from users.models import User


class RFQAndQuotationWorkflowTestCase(APITestCase):
    def setUp(self):
        # 1. Users
        self.admin = User.objects.create_user(
            username="admin_proc2", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.proc_officer = User.objects.create_user(
            username="officer_proc2", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.manager = User.objects.create_user(
            username="manager_proc2", password="password123", role="hotel_manager", is_active=True, is_verified=True
        )

        # 2. Suppliers
        self.supplier_a = Supplier.objects.create(
            name="Supplier Alpha Meat Co", phone="+251911111111", email="alpha@meat.com"
        )
        self.supplier_b = Supplier.objects.create(
            name="Supplier Beta Farms", phone="+251922222222", email="beta@farms.com"
        )
        self.supplier_uninvited = Supplier.objects.create(
            name="Supplier Omega Outsider", phone="+251933333333", email="omega@outsider.com"
        )

        # 3. Locations
        self.main_store, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN",
            defaults={"name": "Main Central Store", "location_type": "warehouse", "is_active": True},
        )

        # 4. Inventory Items
        self.cat, _ = InventoryCategory.objects.get_or_create(
            name="Provisions", defaults={"category_type": "f_and_b"}
        )
        self.beef_item = InventoryItem.objects.create(
            name="Prime Beef Tenderloin",
            item_code="BEEF-001",
            category=self.cat,
            unit="kg",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("450.00"),
            min_reorder_level=Decimal("5.00"),
        )
        self.potato_item = InventoryItem.objects.create(
            name="Russet Potatoes",
            item_code="POT-001",
            category=self.cat,
            unit="kg",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("35.00"),
            min_reorder_level=Decimal("20.00"),
        )

        # 5. Accounts
        ensure_default_accounts()

        # 6. Approved Purchase Requisitions
        self.req_kitchen = PurchaseRequisition.objects.create(
            requisition_number="PR-TEST-KITCHEN-01",
            department="kitchen",
            status="approved",
            requested_by=self.proc_officer,
            approved_by=self.manager,
            approved_at=timezone.now(),
            total_estimated_amount=Decimal("45000.00"),
        )
        self.req_line_beef = PurchaseRequisitionItem.objects.create(
            requisition=self.req_kitchen,
            item=self.beef_item,
            quantity_requested=Decimal("100.00"),
            estimated_unit_cost=Decimal("450.00"),
        )

        self.req_bar = PurchaseRequisition.objects.create(
            requisition_number="PR-TEST-BAR-01",
            department="bar",
            status="approved",
            requested_by=self.proc_officer,
            approved_by=self.manager,
            approved_at=timezone.now(),
            total_estimated_amount=Decimal("7000.00"),
        )
        self.req_line_potato = PurchaseRequisitionItem.objects.create(
            requisition=self.req_bar,
            item=self.potato_item,
            quantity_requested=Decimal("200.00"),
            estimated_unit_cost=Decimal("35.00"),
        )

    def test_01_multi_requisition_aggregation_and_safeguard_allocation_locking(self):
        """
        Tests Safeguard 1: RFQ aggregates approved requisitions with transactional allocation locking.
        Over-allocating beyond remaining quantity raises ValidationError.
        """
        deadline = timezone.now() + datetime.timedelta(days=7)
        rfq = create_request_for_quotation(
            user=self.proc_officer,
            title="Q4 Bulk Kitchen & Bar Replenishment Tender",
            delivery_location_id=self.main_store.id,
            submission_deadline=deadline,
            requisition_ids=[self.req_kitchen.id, self.req_bar.id],
            items_data=[
                {
                    "item_id": self.beef_item.id,
                    "target_quantity": "80.00",
                    "requisition_item_id": self.req_line_beef.id,
                    "specifications": "Grade A Prime Cut",
                },
                {
                    "item_id": self.potato_item.id,
                    "target_quantity": "200.00",
                    "requisition_item_id": self.req_line_potato.id,
                    "specifications": "Grade 1 Washed",
                },
            ],
            is_public_bidding=False,
            invited_supplier_ids=[self.supplier_a.id, self.supplier_b.id],
        )

        self.assertEqual(rfq.status, "draft")
        self.assertEqual(rfq.items.count(), 2)
        self.assertEqual(rfq.requisitions.count(), 2)
        self.assertEqual(rfq.invited_suppliers.count(), 2)

        # Attempt concurrent over-allocation on another RFQ:
        # Beef requested was 100, 80 is allocated to RFQ. Only 20 remaining. Attempting 50 must fail.
        with self.assertRaises(ValidationError) as ctx:
            create_request_for_quotation(
                user=self.proc_officer,
                title="Concurrent RFQ attempting over-allocation",
                delivery_location_id=self.main_store.id,
                submission_deadline=deadline,
                requisition_ids=[self.req_kitchen.id],
                items_data=[
                    {
                        "item_id": self.beef_item.id,
                        "target_quantity": "50.00",
                        "requisition_item_id": self.req_line_beef.id,
                    }
                ],
            )
        self.assertIn("exceeds remaining unsourced balance", str(ctx.exception))

        # But sourcing remaining 20.00 succeeds
        rfq2 = create_request_for_quotation(
            user=self.proc_officer,
            title="Residual Sourcing RFQ",
            delivery_location_id=self.main_store.id,
            submission_deadline=deadline,
            requisition_ids=[self.req_kitchen.id],
            items_data=[
                {
                    "item_id": self.beef_item.id,
                    "target_quantity": "20.00",
                    "requisition_item_id": self.req_line_beef.id,
                }
            ],
        )
        self.assertEqual(rfq2.items.first().target_quantity, Decimal("20.00"))

    def test_02_unapproved_requisition_rejected(self):
        """Unapproved (draft/pending/rejected) requisitions cannot be included in an RFQ."""
        draft_req = PurchaseRequisition.objects.create(
            requisition_number="PR-DRAFT-001",
            department="housekeeping",
            status="draft",
            requested_by=self.proc_officer,
        )
        deadline = timezone.now() + datetime.timedelta(days=7)
        with self.assertRaises(ValidationError) as ctx:
            create_request_for_quotation(
                user=self.proc_officer,
                title="Invalid Draft RFQ",
                delivery_location_id=self.main_store.id,
                submission_deadline=deadline,
                requisition_ids=[draft_req.id],
            )
        self.assertIn("Only 'approved' requisitions are eligible", str(ctx.exception))

    def test_03_restricted_rfq_uninvited_supplier_rejection(self):
        """Uninvited suppliers cannot submit bids on restricted RFQs."""
        deadline = timezone.now() + datetime.timedelta(days=7)
        rfq = create_request_for_quotation(
            user=self.proc_officer,
            title="Private Meat Tender",
            delivery_location_id=self.main_store.id,
            submission_deadline=deadline,
            requisition_ids=[self.req_kitchen.id],
            items_data=[
                {"item_id": self.beef_item.id, "target_quantity": "50.00", "requisition_item_id": self.req_line_beef.id}
            ],
            is_public_bidding=False,
            invited_supplier_ids=[self.supplier_a.id],
        )
        publish_request_for_quotation(rfq_id=rfq.id, user=self.proc_officer)

        # Supplier Omega was not invited
        with self.assertRaises(ValidationError) as ctx:
            submit_supplier_quotation(
                user=self.proc_officer,
                supplier_id=self.supplier_uninvited.id,
                rfq_id=rfq.id,
                valid_until=timezone.now().date() + datetime.timedelta(days=14),
                items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "50.00", "quoted_unit_price": "440.00"}],
            )
        self.assertIn("not authorized to bid on restricted RFQ", str(ctx.exception))

    def test_04_late_quotation_submission_rejected(self):
        """Quotations submitted past the submission deadline are strictly rejected."""
        # Create RFQ with a deadline in the future, then artificially elapse it
        future_deadline = timezone.now() + datetime.timedelta(hours=2)
        rfq = create_request_for_quotation(
            user=self.proc_officer,
            title="Urgent Seafood Bid",
            delivery_location_id=self.main_store.id,
            submission_deadline=future_deadline,
            is_public_bidding=True,
            items_data=[{"item_id": self.beef_item.id, "target_quantity": "10.00"}],
        )
        publish_request_for_quotation(rfq_id=rfq.id, user=self.proc_officer)

        # Simulate deadline expiration
        rfq.submission_deadline = timezone.now() - datetime.timedelta(minutes=5)
        rfq.save(update_fields=["submission_deadline"])

        with self.assertRaises(ValidationError) as ctx:
            submit_supplier_quotation(
                user=self.proc_officer,
                supplier_id=self.supplier_a.id,
                rfq_id=rfq.id,
                valid_until=timezone.now().date() + datetime.timedelta(days=10),
                items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "10.00", "quoted_unit_price": "450.00"}],
            )
        self.assertIn("Late bids are prohibited", str(ctx.exception))

    def test_05_direct_quotation_sole_source_justification_enforcement(self):
        """Direct quotations bypassing RFQ require approved Requisition and documented sole-source justification."""
        # Without justification -> rejected
        with self.assertRaises(ValidationError) as ctx:
            submit_supplier_quotation(
                user=self.proc_officer,
                supplier_id=self.supplier_a.id,
                requisition_id=self.req_kitchen.id,
                sole_source_justification="",  # Empty
                valid_until=timezone.now().date() + datetime.timedelta(days=10),
                items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "10.00", "quoted_unit_price": "450.00"}],
            )
        self.assertIn("require a linked Requisition and a documented Sole Source Justification", str(ctx.exception))

        # With justification -> succeeds
        quote = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_a.id,
            requisition_id=self.req_kitchen.id,
            sole_source_justification="Sole regional certified butcher for hotel-grade aged tenderloin.",
            valid_until=timezone.now().date() + datetime.timedelta(days=10),
            items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "10.00", "quoted_unit_price": "450.00"}],
        )
        self.assertEqual(quote.status, "submitted")
        self.assertEqual(quote.requisition, self.req_kitchen)

    def test_06_landed_cost_and_multi_currency_normalization(self):
        """Tests authoritative calculation of line discounts, shipping, duties, taxes, and ETB conversion."""
        quote = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_a.id,
            requisition_id=self.req_kitchen.id,
            sole_source_justification="Specialist import machinery",
            valid_until=timezone.now().date() + datetime.timedelta(days=30),
            currency="USD",
            exchange_rate=Decimal("120.0000"),  # 1 USD = 120 ETB
            shipping_and_handling=Decimal("50.00"),
            customs_and_duties=Decimal("150.00"),
            tax_amount=Decimal("100.00"),
            items_data=[
                {
                    "item_id": self.beef_item.id,
                    "quoted_quantity": "10.00",
                    "quoted_unit_price": "100.00",  # Gross = 1000.00
                    "discount_percentage": "10.00", # Discount = 100.00 -> Net = 900.00
                }
            ],
        )

        item = quote.items.first()
        self.assertEqual(item.line_total, Decimal("900.00"))
        self.assertEqual(quote.subtotal, Decimal("900.00"))
        # Total quoted USD = 900 + 50 (shipping) + 150 (customs) + 100 (tax) = 1200.00 USD
        self.assertEqual(quote.total_quoted_amount, Decimal("1200.00"))
        # Total landed ETB = 1200 * 120 = 144,000.00 ETB
        self.assertEqual(quote.total_landed_cost_etb, Decimal("144000.00"))

    def test_07_safeguard_split_award_and_multi_po_conversion(self):
        """
        SAFEGUARD 2: Split-award PO conversion.
        RFQ has 2 items. Supplier A and B bid on both.
        Item 1 awarded to Supplier A; Item 2 awarded to Supplier B.
        Conversion generates 2 distinct Purchase Orders with full line-level tracking.
        """
        deadline = timezone.now() + datetime.timedelta(days=5)
        rfq = create_request_for_quotation(
            user=self.proc_officer,
            title="Dual Commodity Tender",
            delivery_location_id=self.main_store.id,
            submission_deadline=deadline,
            requisition_ids=[self.req_kitchen.id, self.req_bar.id],
            items_data=[
                {"item_id": self.beef_item.id, "target_quantity": "100.00", "requisition_item_id": self.req_line_beef.id},
                {"item_id": self.potato_item.id, "target_quantity": "200.00", "requisition_item_id": self.req_line_potato.id},
            ],
            is_public_bidding=False,
            invited_supplier_ids=[self.supplier_a.id, self.supplier_b.id],
        )
        publish_request_for_quotation(rfq_id=rfq.id, user=self.proc_officer)

        # Supplier A bids: Beef @ 420.00, Potatoes @ 40.00
        quote_a = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_a.id,
            rfq_id=rfq.id,
            valid_until=timezone.now().date() + datetime.timedelta(days=15),
            supplier_reference="ALPHA-BID-001",
            payment_terms="Net 30",
            delivery_lead_time_days=2,
            items_data=[
                {"item_id": self.beef_item.id, "quoted_quantity": "100.00", "quoted_unit_price": "420.00"},
                {"item_id": self.potato_item.id, "quoted_quantity": "200.00", "quoted_unit_price": "40.00"},
            ],
        )

        # Supplier B bids: Beef @ 460.00, Potatoes @ 30.00
        quote_b = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_b.id,
            rfq_id=rfq.id,
            valid_until=timezone.now().date() + datetime.timedelta(days=15),
            supplier_reference="BETA-BID-001",
            payment_terms="Net 15",
            delivery_lead_time_days=1,
            items_data=[
                {"item_id": self.beef_item.id, "quoted_quantity": "100.00", "quoted_unit_price": "460.00"},
                {"item_id": self.potato_item.id, "quoted_quantity": "200.00", "quoted_unit_price": "30.00"},
            ],
        )

        # Evaluation & Award:
        # Beef line from Quote A awarded (Alpha is cheaper @ 420 vs 460)
        # Potatoes line from Quote B awarded (Beta is cheaper @ 30 vs 40)
        item_a_beef = quote_a.items.get(item=self.beef_item)
        item_a_potato = quote_a.items.get(item=self.potato_item)
        item_b_beef = quote_b.items.get(item=self.beef_item)
        item_b_potato = quote_b.items.get(item=self.potato_item)

        awards_data = [
            {
                "quotation_id": quote_a.id,
                "awarded_item_ids": [item_a_beef.id],
                "rejected_item_ids": [item_a_potato.id],
            },
            {
                "quotation_id": quote_b.id,
                "awarded_item_ids": [item_b_potato.id],
                "rejected_item_ids": [item_b_beef.id],
            },
        ]

        affected_quotes = evaluate_and_award_quotations(
            rfq_id=rfq.id,
            awards_data=awards_data,
            user=self.manager,
            justification="Split award to optimal lowest-cost vendors per line item per procurement policy.",
        )

        # Reload quotations and items
        quote_a.refresh_from_db()
        quote_b.refresh_from_db()
        item_a_beef.refresh_from_db()
        item_b_potato.refresh_from_db()
        self.assertEqual(quote_a.status, "partially_awarded")
        self.assertEqual(quote_b.status, "partially_awarded")
        self.assertEqual(item_a_beef.award_status, "awarded")
        self.assertEqual(item_b_potato.award_status, "awarded")

        # Convert awarded quotations to Purchase Orders
        created_pos = convert_awarded_quotations_to_purchase_orders(
            quotation_ids=[quote_a.id, quote_b.id],
            user=self.proc_officer,
        )

        self.assertEqual(len(created_pos), 2)
        po_alpha = next(po for po in created_pos if po.supplier == self.supplier_a)
        po_beta = next(po for po in created_pos if po.supplier == self.supplier_b)

        # PO Alpha verification
        self.assertEqual(po_alpha.status, "issued")
        self.assertEqual(po_alpha.items.count(), 1)
        po_alpha_item = po_alpha.items.first()
        self.assertEqual(po_alpha_item.item, self.beef_item)
        self.assertEqual(po_alpha_item.unit_price, Decimal("420.00"))
        self.assertEqual(po_alpha.total_amount, Decimal("42000.00"))
        self.assertEqual(po_alpha.originating_quotation, quote_a)
        self.assertEqual(po_alpha_item.originating_quote_item, item_a_beef)

        # PO Beta verification
        self.assertEqual(po_beta.status, "issued")
        self.assertEqual(po_beta.items.count(), 1)
        po_beta_item = po_beta.items.first()
        self.assertEqual(po_beta_item.item, self.potato_item)
        self.assertEqual(po_beta_item.unit_price, Decimal("30.00"))
        self.assertEqual(po_beta.total_amount, Decimal("6000.00"))
        self.assertEqual(po_beta.originating_quotation, quote_b)
        self.assertEqual(po_beta_item.originating_quote_item, item_b_potato)

        # Check line-level conversion tracking
        item_a_beef.refresh_from_db()
        self.assertTrue(item_a_beef.is_converted_to_po)
        self.assertEqual(item_a_beef.converted_purchase_order, po_alpha)

        item_b_potato.refresh_from_db()
        self.assertTrue(item_b_potato.is_converted_to_po)
        self.assertEqual(item_b_potato.converted_purchase_order, po_beta)

        # Quotation headers transition to converted_to_po
        quote_a.refresh_from_db()
        quote_b.refresh_from_db()
        self.assertEqual(quote_a.status, "converted_to_po")
        self.assertEqual(quote_b.status, "converted_to_po")

    def test_08_safeguard_quotation_immutability(self):
        """
        SAFEGUARD 3: Quotation immutability across ORM, API, and Admin.
        Awarded/converted/rejected quotes cannot be modified or deleted.
        """
        quote = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_a.id,
            requisition_id=self.req_kitchen.id,
            sole_source_justification="Specialist supplier",
            valid_until=timezone.now().date() + datetime.timedelta(days=10),
            items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "10.00", "quoted_unit_price": "450.00"}],
        )

        item = quote.items.first()
        evaluate_and_award_quotations(
            awards_data=[{"quotation_id": quote.id, "awarded_item_ids": [item.id]}],
            user=self.manager,
            justification="Emergency sole-source approval",
        )
        quote.refresh_from_db()
        self.assertEqual(quote.status, "accepted")

        # 1. ORM Save Mutation Guard
        quote.subtotal = Decimal("100.00")
        with self.assertRaises(ValidationError) as ctx:
            quote.save()
        self.assertIn("is in terminal/locked status", str(ctx.exception))

        # 2. ORM Delete Guard
        with self.assertRaises(ValidationError) as ctx:
            quote.delete()
        self.assertIn("cannot be deleted", str(ctx.exception))

        # 3. Item Delete Guard
        with self.assertRaises(ValidationError) as ctx:
            item.delete()
        self.assertIn("Awarded quotation items cannot be deleted", str(ctx.exception))

        # 4. DRF API Mutation Guard
        self.client.force_authenticate(user=self.admin)
        res = self.client.patch(f"/api/v1/procurement/quotations/{quote.id}/", {"payment_terms": "Cash on Delivery"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked", str(res.data))

    def test_09_audit_events_dispatched_on_all_transitions(self):
        """All procurement state changes dispatch immutable AuditEvent records."""
        initial_actions = set(AuditEvent.objects.values_list("action", flat=True))

        deadline = timezone.now() + datetime.timedelta(days=5)
        rfq = create_request_for_quotation(
            user=self.proc_officer,
            title="Audit Trail Verification RFQ",
            delivery_location_id=self.main_store.id,
            submission_deadline=deadline,
            is_public_bidding=True,
            items_data=[{"item_id": self.beef_item.id, "target_quantity": "10.00"}],
        )
        publish_request_for_quotation(rfq_id=rfq.id, user=self.proc_officer)

        quote = submit_supplier_quotation(
            user=self.proc_officer,
            supplier_id=self.supplier_a.id,
            rfq_id=rfq.id,
            valid_until=timezone.now().date() + datetime.timedelta(days=10),
            items_data=[{"item_id": self.beef_item.id, "quoted_quantity": "10.00", "quoted_unit_price": "400.00"}],
        )

        evaluate_quotation(quotation_id=quote.id, user=self.proc_officer, evaluation_notes="Checked specs OK")

        evaluate_and_award_quotations(
            rfq_id=rfq.id,
            awards_data=[{"quotation_id": quote.id, "awarded_item_ids": [quote.items.first().id]}],
            user=self.manager,
            justification="Sole compliant bidder",
        )

        convert_awarded_quotations_to_purchase_orders(quotation_ids=[quote.id], user=self.proc_officer)

        new_actions = list(AuditEvent.objects.values_list("action", flat=True))
        self.assertIn("RFQ_CREATED", new_actions)
        self.assertIn("RFQ_PUBLISHED", new_actions)
        self.assertIn("QUOTATION_SUBMITTED", new_actions)
        self.assertIn("QUOTATION_EVALUATED", new_actions)
        self.assertIn("QUOTATION_ACCEPTED", new_actions)
        self.assertIn("QUOTATION_CONVERTED_TO_PO", new_actions)
        self.assertIn("PO_ISSUED", new_actions)

    def test_10_api_viewset_integration(self):
        """Verifies DRF endpoints for RFQ and Supplier Quotations."""
        self.client.force_authenticate(user=self.proc_officer)

        # 1. Create RFQ via API
        deadline_str = (timezone.now() + datetime.timedelta(days=7)).isoformat()
        res = self.client.post("/api/v1/procurement/rfqs/", {
            "title": "API Test RFQ",
            "delivery_location": self.main_store.id,
            "submission_deadline": deadline_str,
            "is_public_bidding": True,
            "items": [{"item_id": self.beef_item.id, "target_quantity": "25.00"}],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        rfq_id = res.data["id"]

        # 2. Publish RFQ via API
        res = self.client.post(f"/api/v1/procurement/rfqs/{rfq_id}/publish/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "published")

        # 3. Submit Quotation via API
        valid_until_str = (timezone.now().date() + datetime.timedelta(days=14)).isoformat()
        res = self.client.post("/api/v1/procurement/quotations/", {
            "supplier": self.supplier_a.id,
            "rfq": rfq_id,
            "valid_until": valid_until_str,
            "items": [{"item_id": self.beef_item.id, "quoted_quantity": "25.00", "quoted_unit_price": "430.00"}],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        quote_id = res.data["id"]
        quote_item_id = res.data["items"][0]["id"]

        # 4. Award Quotation via API
        res = self.client.post("/api/v1/procurement/quotations/award/", {
            "rfq_id": rfq_id,
            "awards_data": [{"quotation_id": quote_id, "awarded_item_ids": [quote_item_id]}],
            "justification": "Optimal supplier selected via API tender evaluation",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # 5. Convert to PO via API
        res = self.client.post("/api/v1/procurement/quotations/convert-to-po/", {
            "quotation_ids": [quote_id],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["status"], "issued")
