"""Reservations API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
import users.views as legacy_views
from hotel.integrity import record_stock_change, reverse_stock_transaction, transition_reservation


def finalize_paid_reservation(*args, **kwargs):
    return legacy_views.finalize_paid_reservation(*args, **kwargs)


def verify_chapa_transaction(*args, **kwargs):
    return legacy_views.verify_chapa_transaction(*args, **kwargs)


from .selectors import select_reservations

class ReserveRoomNowView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status in ["Occupied", "Maintenance"]:
            return Response(
                {"error": f"Room {room.room_number} is currently {room.status.lower()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = request.data.get("source") or "reception"
        if source == "public" and not room.is_available_online:
            return Response(
                {"error": "This room is not enabled for online booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        guest_name = request.data.get("guest_name") or "Guest"
        guest_email = request.data.get("guest_email") or ""
        guest_phone = request.data.get("guest_phone") or ""
        adults = int(request.data.get("adults") or 1)
        children = int(request.data.get("children") or 0)
        notes = request.data.get("notes") or ""

        try:
            check_in_date = datetime.fromisoformat(request.data.get("check_in_date")).date()
            check_out_date = datetime.fromisoformat(request.data.get("check_out_date")).date()
        except Exception:
            return Response({"error": "Check-in and check-out dates are required."}, status=status.HTTP_400_BAD_REQUEST)

        if check_out_date <= check_in_date:
            return Response({"error": "Check-out must be after check-in."}, status=status.HTTP_400_BAD_REQUEST)

        _, total_amount, deposit_amount = calculate_reservation_amounts(room, check_in_date, check_out_date)

        reservation = create_reservation_safely(
            room_id=room.id,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            adults=adults,
            children=children,
            notes=notes,
            source=source,
            total_amount=total_amount,
            deposit_amount=deposit_amount,
        )
        reservation.ensure_tokens()

        if source == "reception" and str(request.data.get("pay_now", "false")).lower() != "true":
            reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="confirmed")
            reservation.payment_status = "pending"
            reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "status", "payment_status", "updated_at"])
            room.status = "Reserved"
            room.booking_source = "front_desk"
            room.save(update_fields=["status", "booking_source"])
            summary = send_reservation_confirmation(reservation)
            return Response(
                {
                    "message": "Reception reservation created successfully.",
                    "reservation": summary,
                },
                status=status.HTTP_201_CREATED,
            )

        attempt, _ = get_or_create_payment_attempt(
            target=reservation,
            expected_amount=deposit_amount,
            idempotency_key=request.headers.get("Idempotency-Key") or f"reservation-deposit-{reservation.pk}-{deposit_amount}",
            currency="ETB",
        )
        tx_ref = attempt.provider_tx_ref
        callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
        return_url = f"{create_public_reservation_url(reservation, request=request)}?payment=returned"
        payload = {
            "amount": str(deposit_amount),
            "currency": "ETB",
            "email": guest_email or "guest@example.com",
            "first_name": guest_name,
            "last_name": room.name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": "Room Deposit",
                "description": f"Reservation for room {room.room_number} from {check_in_date.isoformat()} to {check_out_date.isoformat()}",
            },
            "meta": {
                "reservation_id": reservation.id,
                "room_id": room.id,
                "room_number": room.room_number,
                "check_in_date": check_in_date.isoformat(),
                "check_out_date": check_out_date.isoformat(),
                "booking_source": source,
            },
        }

        try:
            chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
            checkout_url = (
                chapa_response.get("data", {}).get("checkout_url")
                or chapa_response.get("data", {}).get("link")
                or chapa_response.get("checkout_url")
            )
            if not checkout_url:
                raise ValueError("Chapa did not return a checkout URL.")
        except ValueError as exc:
            reservation.payment_status = "failed"
            reservation.save(update_fields=["payment_status", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        reservation.chapa_tx_ref = tx_ref
        reservation.chapa_checkout_url = checkout_url
        reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "chapa_tx_ref", "chapa_checkout_url", "updated_at"])
        attempt.status = "initiated"
        attempt.safe_metadata = {"checkout_url": checkout_url, "payment_type": "deposit"}
        attempt.save(update_fields=["status", "safe_metadata", "updated_at"])
        room.status = "Reserved"
        room.booking_source = "online" if source == "public" else "front_desk"
        room.save(update_fields=["status", "booking_source"])

        return Response(
            {
                "message": "Reservation created successfully.",
                "checkout_url": checkout_url,
                "amount": float(deposit_amount),
                "tx_ref": tx_ref,
                "reservation": build_reservation_summary(reservation),
            },
            status=status.HTTP_201_CREATED,
        )


class UpdateRoomFrontDeskStatusView(APIView):
    permission_classes = [IsReservationOperator]

    def patch(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        reservation = None
        reservation_id = request.data.get("reservation_id")
        if reservation_id:
            reservation = Reservation.objects.filter(id=reservation_id, room=room).first()

        if action == "checkin":
            pay_method = request.data.get("payment_method", "Cash")
            pay_ref = request.data.get("payment_reference", "")
            
            is_prepaid = reservation and reservation.payment_status == "paid"
            
            room.status = "Occupied"
            if reservation:
                reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_in")
                reservation.checked_in_at = timezone.now()
                
                nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
                room_total = to_decimal(room.base_price) * nights
                
                if not is_prepaid:
                    reservation.payment_status = "paid"
                    if pay_ref:
                        reservation.payment_reference = f"{pay_method} - {pay_ref}"
                    else:
                        reservation.payment_reference = pay_method
                    reservation.total_amount = room_total
                
                reservation.save()

                if not is_prepaid:
                    RoomHistory.objects.create(
                        room=room,
                        event_type="checkin",
                        guest_name=reservation.guest_name,
                        check_in_date=reservation.check_in_date,
                        check_out_date=reservation.check_out_date,
                        revenue=room_total,
                        payment_method=pay_method,
                        notes=f"Check-in payment via {pay_method}",
                    )
        elif action == "checkout":
            room.status = "Cleaning"
            if reservation:
                reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_out")
                reservation.checked_out_at = timezone.now()
                reservation.save(update_fields=["status", "checked_out_at", "updated_at"])
        else:
            return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

        room.booking_source = request.data.get("booking_source") or room.booking_source
        room.save(update_fields=["status", "booking_source"])
        return Response({"message": "Room status updated.", "status": room.status})


class PublicRoomCatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            check_in_param = request.query_params.get("check_in_date")
            check_out_param = request.query_params.get("check_out_date")
            online_qs = Room.objects.filter(is_available_online=True).order_by("priority", "room_number")
            qs = online_qs if online_qs.exists() else Room.objects.all().order_by("priority", "room_number")
            
            print(f"DEBUG: Found {qs.count()} rooms total.")
            payload = []
            for room in qs:
                is_available = True
                if check_in_param and check_out_param:
                    try:
                        check_in_date = datetime.fromisoformat(check_in_param).date()
                        check_out_date = datetime.fromisoformat(check_out_param).date()
                        is_available = not reservation_overlaps(room, check_in_date, check_out_date)
                    except Exception as e:
                        print(f"DEBUG: Date error for room {room.id}: {e}")
                        is_available = True

                image_url = None
                if room.main_image:
                    try:
                        image_url = request.build_absolute_uri(room.main_image.url)
                    except:
                        image_url = room.main_image.name # fallback
                        
                image_2_url = None
                if room.image_2:
                    try:
                        image_2_url = request.build_absolute_uri(room.image_2.url)
                    except:
                        image_2_url = room.image_2.name # fallback
                        
                image_3_url = None
                if room.image_3:
                    try:
                        image_3_url = request.build_absolute_uri(room.image_3.url)
                    except:
                        image_3_url = room.image_3.name # fallback
                
                payload.append({
                    "id": room.id,
                    "name": room.name,
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "description": room.description,
                    "base_price": float(room.base_price or 0.0),
                    "weekend_price": float(room.weekend_price or room.base_price or 0.0),
                    "main_image": image_url,
                    "image_2": image_2_url,
                    "image_3": image_3_url,
                    "amenities": room.amenities or [],
                    "common_amenities": room.common_amenities or [],
                    "max_adults": room.max_adults,
                    "max_children": room.max_children,
                    "check_in_time": str(room.check_in_time),
                    "check_out_time": str(room.check_out_time),
                    "min_stay": room.min_stay,
                    "is_available": is_available and room.status not in ["Occupied", "Maintenance"],
                    "is_online_enabled": bool(room.is_available_online),
                    "deposit_type": room.online_deposit_type,
                    "deposit_amount": float(room.advance_payment_amount or 0),
                })
            print(f"DEBUG: Returning {len(payload)} items.")
            return Response(payload)
        except Exception as e:
            logger.exception("Public room catalog failed")
            return Response({"error": "Unable to load room catalog."}, status=500)


class ReservationListView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request):
        reservations = select_reservations(request.query_params)
        paginator = V1PageNumberPagination()
        page = paginator.paginate_queryset(reservations, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(ReservationSerializer(page, many=True).data)
        return Response(ReservationSerializer(reservations[:100], many=True).data)


class PublicRoomReserveView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, room_id):
        try:
            online_rooms_exist = Room.objects.filter(is_available_online=True).exists()
            try:
                if online_rooms_exist:
                    room = Room.objects.get(id=room_id, is_available_online=True)
                else:
                    room = Room.objects.get(id=room_id)
            except Room.DoesNotExist:
                return Response({"error": "Room not found or not available online."}, status=404)

            try:
                check_in_date = datetime.fromisoformat(request.data.get("check_in_date")).date()
                check_out_date = datetime.fromisoformat(request.data.get("check_out_date")).date()
            except Exception:
                return Response({"error": "Valid check-in and check-out dates are required."}, status=400)

            if check_out_date <= check_in_date:
                return Response({"error": "Check-out must be after check-in."}, status=400)
            guest_name = request.data.get("guest_name") or "Guest"
            guest_email = request.data.get("guest_email") or ""
            guest_phone = request.data.get("guest_phone") or ""
            adults = int(request.data.get("adults") or 1)
            children = int(request.data.get("children") or 0)
            notes = request.data.get("notes") or ""
            _, total_amount, deposit_amount = calculate_reservation_amounts(room, check_in_date, check_out_date)

            reservation = create_reservation_safely(
                room_id=room.id,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=guest_phone,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adults=adults,
                children=children,
                notes=notes,
                source="public",
                total_amount=total_amount,
                deposit_amount=deposit_amount,
            )
            reservation.ensure_tokens()

            attempt, _ = get_or_create_payment_attempt(
                target=reservation,
                expected_amount=deposit_amount,
                idempotency_key=request.headers.get("Idempotency-Key") or f"reservation-deposit-{reservation.pk}-{deposit_amount}",
                currency="ETB",
            )
            tx_ref = attempt.provider_tx_ref
            callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
            return_url = f"{create_public_reservation_url(reservation, request=request)}?payment=returned"
            payload = {
                "amount": str(deposit_amount),
                "currency": "ETB",
                "email": guest_email or "guest@example.com",
                "first_name": guest_name,
                "last_name": room.name,
                "tx_ref": tx_ref,
                "callback_url": callback_url,
                "return_url": return_url,
                "customization": {
                    "title": "Room Deposit",
                    "description": f"Room {room.room_number} from {check_in_date.isoformat()} to {check_out_date.isoformat()}",
                },
                "meta": {
                    "reservation_id": reservation.id,
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "check_in_date": check_in_date.isoformat(),
                    "check_out_date": check_out_date.isoformat(),
                    "booking_source": "public",
                },
            }

            try:
                chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
                checkout_url = (
                    chapa_response.get("data", {}).get("checkout_url")
                    or chapa_response.get("data", {}).get("link")
                    or chapa_response.get("checkout_url")
                )
                if not checkout_url:
                    raise ValueError("Chapa did not return a checkout URL.")
            except ValueError as exc:
                reservation.payment_status = "failed"
                reservation.save(update_fields=["payment_status", "updated_at"])
                return Response({"error": str(exc)}, status=400)

            reservation.chapa_tx_ref = tx_ref
            reservation.chapa_checkout_url = checkout_url
            reservation.save(update_fields=["confirmation_code", "qr_token", "public_token", "chapa_tx_ref", "chapa_checkout_url", "updated_at"])
            room.status = "Reserved"
            attempt.status = "initiated"
            attempt.safe_metadata = {"checkout_url": checkout_url, "payment_type": "deposit"}
            attempt.save(update_fields=["status", "safe_metadata", "updated_at"])
            room.booking_source = "online"
            room.save(update_fields=["status", "booking_source"])

            return Response(
                {
                    "message": "Public reservation created successfully.",
                    "checkout_url": checkout_url,
                    "reservation": build_reservation_summary(reservation),
                },
                status=201,
            )
        except Exception as e:
            logger.exception("Public room reservation failed")
            return Response({"error": "Unable to create reservation."}, status=500)


class PublicReservationDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            reservation = get_public_reservation_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)
        return Response(build_reservation_summary(reservation))


class PublicReservationVerifyPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            reservation = get_public_reservation_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if reservation.payment_status == "paid":
            return Response({"message": "Payment already verified.", "reservation": send_reservation_confirmation(reservation)})

        tx_ref = request.data.get("tx_ref") or reservation.chapa_tx_ref
        if not tx_ref:
            return Response({"error": "No pending Chapa transaction found for this reservation."}, status=400)

        if not reservation.chapa_tx_ref or not hmac.compare_digest(
            str(tx_ref), str(reservation.chapa_tx_ref)
        ):
            return Response(
                {"error": "Payment transaction does not belong to this reservation."}, status=400
            )
        try:
            verification = verify_chapa_transaction(tx_ref)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment is still pending.", "status": status_value or "pending"}, status=202)

        try:
            attempt = PaymentAttempt.objects.get(provider_tx_ref=tx_ref, reservation=reservation)
        except PaymentAttempt.DoesNotExist:
            attempt = PaymentAttempt.objects.create(
                provider="chapa", purpose="reservation_deposit", reservation=reservation,
                expected_amount=reservation.deposit_amount, currency="ETB",
                provider_tx_ref=tx_ref,
                idempotency_key=f"legacy-reservation-{reservation.pk}-{tx_ref}"[:120],
                status="initiated", safe_metadata={"legacy_backfill": True},
            )
        try:
            validate_chapa_payment(
                verification_data,
                expected_tx_ref=attempt.provider_tx_ref,
                expected_amount=attempt.expected_amount,
                expected_currency=attempt.currency,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
            summary = finalize_paid_reservation(
                reservation, payment_reference=tx_ref, payment_attempt=attempt,
            )
            mark_payment_attempt_verified(
                tx_ref=tx_ref,
                provider_event_ref=str(verification_data.get("reference") or verification_data.get("id") or "") or None,
                safe_metadata={"status": status_value, "currency": attempt.currency, "purpose": attempt.purpose},
            )
        return Response({"message": "Reservation payment verified successfully.", "reservation": summary})


class PublicQRCheckInView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request):
        qr_token = request.data.get("qr_token")
        if not qr_token:
            return Response({"error": "QR token is required."}, status=400)
        reservation = Reservation.objects.select_related("room").filter(
            models.Q(qr_token=qr_token) | models.Q(confirmation_code=qr_token)
        ).first()
        if not reservation:
            return Response({"error": "Reservation not found with this code or QR."}, status=404)

        reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_in")
        reservation.checked_in_at = timezone.now()
        reservation.save(update_fields=["status", "checked_in_at", "updated_at"])
        reservation.room.status = "Occupied"
        reservation.room.booking_source = "front_desk"
        reservation.room.save(update_fields=["status", "booking_source"])
        return Response({"message": "Guest checked in successfully.", "reservation": build_reservation_summary(reservation)})


class GuestProfileView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request):
        phone = request.query_params.get("phone")
        reservation_id = request.query_params.get("reservation_id")
        qs = GuestProfile.objects.all()
        if phone:
            qs = qs.filter(phone__icontains=phone)
        if reservation_id:
            qs = qs.filter(reservation_id=reservation_id)
        return Response(GuestProfileSerializer(qs[:50], many=True).data)

    def post(self, request):
        serializer = GuestProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class GuestProfileDetailView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request, pk):
        try:
            profile = GuestProfile.objects.get(pk=pk)
        except GuestProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=404)
        return Response(GuestProfileSerializer(profile).data)

    def patch(self, request, pk):
        try:
            profile = GuestProfile.objects.get(pk=pk)
        except GuestProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=404)
        serializer = GuestProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class SecureGuestIdDownloadView(APIView):
    """Deliver sensitive guest identity scan through authorized download endpoint."""
    permission_classes = [IsReservationOperator]

    def get(self, request, pk):
        try:
            profile = GuestProfile.objects.get(pk=pk)
        except GuestProfile.DoesNotExist:
            return Response({"error": "Guest profile not found."}, status=404)

        if not profile.id_scan:
            return Response({"error": "No identity scan available for this guest."}, status=404)

        try:
            scan_file = profile.id_scan.file
        except Exception:
            return Response({"error": "Identity scan file not found on storage."}, status=404)

        import mimetypes
        from django.http import FileResponse
        mime_type, _ = mimetypes.guess_type(profile.id_scan.name)
        response = FileResponse(scan_file, content_type=mime_type or "application/octet-stream")
        response["Content-Disposition"] = f'inline; filename="guest_identity_{pk}.bin"'
        return response



class FolioChargeView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request, reservation_id):
        charges = FolioCharge.objects.filter(reservation_id=reservation_id)
        return Response(FolioChargeSerializer(charges, many=True).data)

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)
        data = request.data.copy()
        data["reservation"] = reservation.id
        data.setdefault("added_by", request.user.username)
        serializer = FolioChargeSerializer(data=data)
        if serializer.is_valid():
            with transaction.atomic():
                folio_charge = serializer.save()
                
                # If an inventory item is linked, check stock and deduct it
                if folio_charge.inventory_item:
                    inv_item = folio_charge.inventory_item
                    qty = to_decimal(folio_charge.quantity)
                    
                    record_stock_change(
                        item_id=inv_item.pk, transaction_type="issuance", quantity=qty,
                        unit_cost=inv_item.unit_cost, reference_number=f"Folio #{reservation.id}",
                        destination_dept="Housekeeping", destination_room=f"Room {reservation.room.room_number}",
                        notes=f"Minibar consumption charge recorded on guest folio (Charge ID #{folio_charge.id}).",
                        logged_by_username=request.user.username,
                    )

                # --- Post General Ledger Journal Entry ---
                try:
                    amount = to_decimal(folio_charge.amount)
                    if amount > 0:
                        post_journal_entry(
                            description=f"Auto JV: Folio Charge - {folio_charge.description} (Res #{reservation.id})",
                            items=[
                                {
                                    "account_code": "1200", # Accounts Receivable
                                    "debit": amount,
                                    "credit": Decimal("0.00")
                                },
                                {
                                    "account_code": "4200", # Folio Extras Revenue
                                    "debit": Decimal("0.00"),
                                    "credit": amount
                                }
                            ]
                        )
                except Exception as e:
                    print(f"GL Auto-post error for Folio charge: {e}")
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class FolioChargeDeleteView(APIView):
    permission_classes = [IsReservationOperator]

    def delete(self, request, charge_id):
        try:
            charge = FolioCharge.objects.get(id=charge_id)
            with transaction.atomic():
                if charge.inventory_item:
                    inv_item = charge.inventory_item
                    qty = to_decimal(charge.quantity)
                    original = StockTransaction.objects.filter(
                        item=inv_item, transaction_type="issuance",
                        notes__contains=f"Charge ID #{charge.id}",
                    ).order_by("timestamp").first()
                    if not original:
                        raise ValidationError("Original stock ledger entry for this folio charge was not found.")
                    reverse_stock_transaction(
                        transaction_id=original.pk,
                        reason=f"Folio charge #{charge.id} deleted by {request.user.username}",
                        logged_by_username=request.user.username,
                    )
                
                # --- Post General Ledger Reversing Journal Entry ---
                try:
                    amount = to_decimal(charge.amount)
                    if amount > 0:
                        post_journal_entry(
                            description=f"Auto JV: Reverse Folio Charge #{charge.id} (Res #{charge.reservation_id})",
                            items=[
                                {
                                    "account_code": "4200", # Folio Extras Revenue
                                    "debit": amount,
                                    "credit": Decimal("0.00")
                                },
                                {
                                    "account_code": "1200", # Accounts Receivable
                                    "debit": Decimal("0.00"),
                                    "credit": amount
                                }
                            ]
                        )
                except Exception as e:
                    print(f"GL Auto-post error for reversing folio charge: {e}")

                charge.delete()
            return Response({"message": "Charge deleted."})
        except FolioCharge.DoesNotExist:
            return Response({"error": "Charge not found."}, status=404)


class GenerateFinalBillView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(reservation.room.base_price) * nights
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)
        grand_total = room_total + extras_total

        settings_obj = get_system_settings()
        return Response({
            "reservation_id": reservation.id,
            "confirmation_code": reservation.confirmation_code,
            "guest_name": reservation.guest_name,
            "guest_phone": reservation.guest_phone,
            "room_name": reservation.room.name,
            "room_number": reservation.room.room_number,
            "check_in_date": reservation.check_in_date.isoformat(),
            "check_out_date": reservation.check_out_date.isoformat(),
            "nights": nights,
            "room_rate": float(reservation.room.base_price),
            "room_total": float(room_total),
            "folio_charges": FolioChargeSerializer(folio_charges, many=True).data,
            "extras_total": float(extras_total),
            "grand_total": float(grand_total),
            "hotel_name": settings_obj.hotel_name,
            "hotel_address": settings_obj.address,
            "hotel_phone": settings_obj.phone_number,
            "tin_number": settings_obj.tin_number,
            "printer_paper_size": settings_obj.printer_paper_size,
        })


class DigitalCheckInView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)

        if room.status == "Maintenance":
            return Response({"error": "Room is under maintenance (Out of Order)."}, status=400)

        # Find the active reservation for this room
        reservation = Reservation.objects.filter(
            room=room, status__in=["confirmed", "pending"]
        ).order_by("-created_at").first()

        with transaction.atomic():
            # Save guest profile if provided
            guest_data = request.data.get("guest_profile", {})
            if guest_data and reservation:
                profile_data = {
                    "reservation": reservation.id,
                    "full_name": guest_data.get("full_name", reservation.guest_name),
                    "phone": guest_data.get("phone", reservation.guest_phone or ""),
                    "nationality": guest_data.get("nationality", ""),
                    "id_type": guest_data.get("id_type", "national_id"),
                    "id_number": guest_data.get("id_number", ""),
                }
                existing = GuestProfile.objects.filter(reservation=reservation).first()
                if existing:
                    GuestProfileSerializer(existing, data=profile_data, partial=True).save() if GuestProfileSerializer(existing, data=profile_data, partial=True).is_valid() else None
                else:
                    s = GuestProfileSerializer(data=profile_data)
                    if s.is_valid():
                        s.save()

            # Handle payment method
            pay_method = request.data.get("payment_method", "Cash")
            pay_ref = request.data.get("payment_reference", "")

            if reservation:
                is_prepaid = reservation.payment_status == "paid"
                nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
                room_total = to_decimal(room.base_price) * nights

                if pay_method == "Digital Payment" and not is_prepaid:
                    # Return session token so frontend can complete digital payment
                    tx_ref = f"checkin-{reservation.id}-{uuid4().hex[:10]}"
                    callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
                    return_url = f"{get_tenant_frontend_base(request=request)}/dashboard?payment=returned&res_id={reservation.id}&room_no={room.room_number}"

                    payload = {
                        "amount": str(room_total),
                        "currency": "ETB",
                        "email": reservation.guest_email or "guest@example.com",
                        "first_name": reservation.guest_name,
                        "last_name": f"Room {room.room_number}",
                        "tx_ref": tx_ref,
                        "callback_url": callback_url,
                        "return_url": return_url,
                        "customization": {
                            "title": "Room Check-in",
                            "description": f"Check-in Room {room.room_number} - Total due ETB {room_total}",
                        },
                        "meta": {
                            "reservation_id": reservation.id,
                            "room_id": room.id,
                            "booking_source": "checkin",
                        },
                    }
                    try:
                        chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
                        checkout_url = (
                            chapa_response.get("data", {}).get("checkout_url")
                            or chapa_response.get("data", {}).get("link")
                            or chapa_response.get("checkout_url")
                        )
                        if not checkout_url:
                            raise ValueError("Chapa did not return a checkout URL.")

                        reservation.chapa_tx_ref = tx_ref
                        reservation.chapa_checkout_url = checkout_url
                        reservation.save(update_fields=["chapa_tx_ref", "chapa_checkout_url", "updated_at"])

                        return Response({
                            "status": "payment_required",
                            "checkout_url": checkout_url,
                            "tx_ref": tx_ref,
                            "grand_total": float(room_total),
                            "reservation_id": reservation.id,
                        })
                    except Exception as exc:
                        logger.exception("Check-in payment initialization failed")
                        return Response({"error": "Unable to initialize payment."}, status=400)

                # For Cash/Bank Transfer or prepaid reservations:
                room.status = "Occupied"
                room.save(update_fields=["status"])

                reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_in")
                reservation.checked_in_at = timezone.now()
                if not is_prepaid:
                    reservation.payment_status = "paid"
                    if pay_ref:
                        reservation.payment_reference = f"{pay_method} - {pay_ref}"
                    else:
                        reservation.payment_reference = pay_method
                    reservation.total_amount = room_total

                reservation.save()

                if not is_prepaid:
                    RoomHistory.objects.create(
                        room=room,
                        event_type="checkin",
                        guest_name=reservation.guest_name,
                        check_in_date=reservation.check_in_date,
                        check_out_date=reservation.check_out_date,
                        revenue=room_total,
                        payment_method=pay_method,
                        notes=f"Check-in by {request.user.username} via {pay_method}",
                    )

                    # --- Post General Ledger Journal Entry ---
                    try:
                        pay_code = "1000" if pay_method == "Cash" else "1010"
                        if room_total > 0:
                            post_journal_entry(
                                description=f"Auto JV: Room Check-in #{reservation.id} payment",
                                items=[
                                    {
                                        "account_code": pay_code,
                                        "debit": room_total,
                                        "credit": Decimal("0.00")
                                    },
                                    {
                                        "account_code": "4000", # Room Revenue
                                        "debit": Decimal("0.00"),
                                        "credit": room_total
                                    }
                                ]
                            )
                    except Exception as e:
                        print(f"GL Auto-post error for checkin payment: {e}")
            else:
                # Fallback if no reservation (though normally check-in requires reservation)
                room.status = "Occupied"
                room.save(update_fields=["status"])

        return Response({
            "message": "Guest checked in successfully.",
            "room_status": room.status,
            "reservation_id": reservation.id if reservation else None,
        })


class EnhancedCheckoutView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        room = reservation.room
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(room.base_price) * nights
        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)
        grand_total = room_total + extras_total

        checkout_revenue = extras_total if reservation.payment_status == "paid" else grand_total

        with transaction.atomic():
            is_prepaid = reservation.payment_status == "paid"

            reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_out")
            reservation.checked_out_at = timezone.now()
            
            pay_status = request.data.get("payment_status", "paid")
            pay_method = request.data.get("payment_method", "Cash")
            pay_ref = request.data.get("payment_reference", "")
            
            reservation.payment_status = pay_status
            if pay_ref:
                reservation.payment_reference = f"{pay_method} - {pay_ref}"
            else:
                reservation.payment_reference = pay_method
            reservation.total_amount = grand_total
            
            reservation.save(update_fields=["status", "checked_out_at", "payment_status", "payment_reference", "total_amount", "updated_at"])

            room.status = "Cleaning"
            room.booking_source = "front_desk"
            room.save(update_fields=["status", "booking_source"])

            RoomHistory.objects.create(
                room=room,
                event_type="checkout",
                guest_name=reservation.guest_name,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
                revenue=checkout_revenue,
                payment_method=pay_method,
                notes=f"Checkout by {request.user.username} via {pay_method}",
            )

            # --- Post General Ledger Journal Entry ---
            try:
                if checkout_revenue > 0:
                    pay_code = "1000" if pay_method == "Cash" else "1010"
                    jv_items = [
                        {
                            "account_code": pay_code,
                            "debit": checkout_revenue,
                            "credit": Decimal("0.00")
                        }
                    ]
                    if is_prepaid:
                        if extras_total > 0:
                            jv_items.append({
                                "account_code": "1200", # Accounts Receivable
                                "debit": Decimal("0.00"),
                                "credit": extras_total
                            })
                    else:
                        if room_total > 0:
                            jv_items.append({
                                "account_code": "4000", # Room Revenue
                                "debit": Decimal("0.00"),
                                "credit": room_total
                            })
                        if extras_total > 0:
                            jv_items.append({
                                "account_code": "1200", # Accounts Receivable
                                "debit": Decimal("0.00"),
                                "credit": extras_total
                            })
                    
                    debit_sum = sum(x["debit"] for x in jv_items)
                    credit_sum = sum(x["credit"] for x in jv_items)
                    diff = debit_sum - credit_sum
                    if diff != 0:
                        target_code = "4000" if room_total > 0 else "1200"
                        for item in jv_items:
                            if item["account_code"] == target_code:
                                item["credit"] += diff
                                break

                    if len(jv_items) >= 2:
                        post_journal_entry(
                            description=f"Auto JV: Room Checkout #{reservation.id} payment",
                            items=jv_items
                        )
            except Exception as e:
                print(f"GL Auto-post error for checkout: {e}")

        settings_obj = get_system_settings()
        return Response({
            "message": "Guest checked out. Room set to Cleaning.",
            "final_bill": {
                "reservation_id": reservation.id,
                "confirmation_code": reservation.confirmation_code,
                "guest_name": reservation.guest_name,
                "guest_phone": reservation.guest_phone,
                "room_name": room.name,
                "room_number": room.room_number,
                "check_in_date": reservation.check_in_date.isoformat(),
                "check_out_date": reservation.check_out_date.isoformat(),
                "nights": nights,
                "room_rate": float(room.base_price),
                "room_total": float(room_total),
                "folio_charges": FolioChargeSerializer(folio_charges, many=True).data,
                "extras_total": float(extras_total),
                "grand_total": float(grand_total),
                "hotel_name": settings_obj.hotel_name,
                "hotel_address": settings_obj.address,
                "hotel_phone": settings_obj.phone_number,
                "tin_number": settings_obj.tin_number,
            },
        })


class CreateCheckoutPaymentSessionView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        payment_type = request.data.get("payment_type", "checkout")  # "checkin" or "checkout"
        room = reservation.room
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(room.base_price) * nights
        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)

        if payment_type == "checkin":
            grand_total = room_total
        else:
            grand_total = extras_total if reservation.payment_status == "paid" else (room_total + extras_total)

        idempotency_key = request.headers.get("Idempotency-Key") or f"reservation-{reservation.pk}-{payment_type}-{grand_total}"
        try:
            attempt, created = get_or_create_payment_attempt(
                target=reservation, expected_amount=grand_total,
                idempotency_key=idempotency_key, currency="ETB", purpose=payment_type,
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=400)
        tx_ref = attempt.provider_tx_ref
        callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/users/payments/chapa/webhook/"
        return_url = f"{get_tenant_frontend_base(request=request)}/dashboard?payment=returned&res_id={reservation.id}&room_no={room.room_number}"
        
        payload = {
            "amount": str(grand_total),
            "currency": "ETB",
            "email": reservation.guest_email or "guest@example.com",
            "first_name": reservation.guest_name,
            "last_name": f"Room {room.room_number}",
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": "Room Check-in" if payment_type == "checkin" else "Hotel Checkout",
                "description": f"{'Check-in' if payment_type == 'checkin' else 'Checkout'} Room {room.room_number} - Total due ETB {grand_total}",
            },
            "meta": {
                "reservation_id": reservation.id,
                "room_id": room.id,
                "booking_source": "checkout",
            },
        }

        try:
            chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
            checkout_url = (
                chapa_response.get("data", {}).get("checkout_url")
                or chapa_response.get("data", {}).get("link")
                or chapa_response.get("checkout_url")
            )
            if not checkout_url:
                raise ValueError("Chapa did not return a checkout URL.")
        except Exception as exc:
            logger.exception("Checkout payment initialization failed")
            return Response({"error": "Unable to initialize payment."}, status=400)
        attempt.status = "initiated"
        attempt.safe_metadata = {"checkout_url": checkout_url, "payment_type": payment_type}
        attempt.save(update_fields=["status", "safe_metadata", "updated_at"])

        reservation.chapa_tx_ref = tx_ref
        reservation.chapa_checkout_url = checkout_url
        reservation.save(update_fields=["chapa_tx_ref", "chapa_checkout_url", "updated_at"])

        return Response({
            "checkout_url": checkout_url,
            "tx_ref": tx_ref,
            "grand_total": float(grand_total),
        })


class VerifyCheckoutPaymentView(APIView):
    permission_classes = [IsReservationOperator]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.select_related("room").get(id=reservation_id)
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found."}, status=404)

        tx_ref = request.data.get("tx_ref") or reservation.chapa_tx_ref
        if not tx_ref:
            return Response({"error": "No pending digital payment session found."}, status=400)

        try:
            verification = verify_chapa_transaction(tx_ref)
        except Exception as exc:
            logger.exception("Checkout payment verification failed")
            return Response({"error": "Unable to verify payment."}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment is still pending.", "status": status_value}, status=202)

        room = reservation.room
        nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        room_total = to_decimal(room.base_price) * nights
        folio_charges = FolioCharge.objects.filter(reservation=reservation)
        extras_total = sum(to_decimal(c.amount) for c in folio_charges)

        if tx_ref.startswith("checkin-"):
            with transaction.atomic():
                reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_in")
                reservation.payment_status = "paid"
                reservation.payment_reference = f"Digital Payment - {tx_ref}"
                reservation.total_amount = room_total
                reservation.checked_in_at = timezone.now()
                reservation.save()

                room.status = "Occupied"
                room.booking_source = "front_desk"
                room.save(update_fields=["status", "booking_source"])

                RoomHistory.objects.create(
                    room=room,
                    event_type="checkin",
                    guest_name=reservation.guest_name,
                    check_in_date=reservation.check_in_date,
                    check_out_date=reservation.check_out_date,
                    revenue=room_total,
                    payment_method="Digital Payment",
                    notes=f"Check-in paid via Chapa (Digital) ref {tx_ref}",
                )

                # --- Post General Ledger Journal Entry ---
                try:
                    if room_total > 0:
                        post_journal_entry(
                            description=f"Auto JV: Room Check-in #{reservation.id} digital payment",
                            items=[
                                {
                                    "account_code": "1010", # Bank Transfer
                                    "debit": room_total,
                                    "credit": Decimal("0.00")
                                },
                                {
                                    "account_code": "4000", # Room Revenue
                                    "debit": Decimal("0.00"),
                                    "credit": room_total
                                }
                            ]
                        )
                except Exception as e:
                    print(f"GL Auto-post error for digital checkin payment: {e}")
            grand_total = room_total
        else:
            checkout_revenue = extras_total if reservation.payment_status == "paid" else (room_total + extras_total)
            is_prepaid = reservation.payment_status == "paid"
            with transaction.atomic():
                reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_out")
                reservation.payment_status = "paid"
                reservation.payment_reference = f"Digital Payment - {tx_ref}"
                reservation.total_amount = room_total + extras_total
                reservation.checked_out_at = timezone.now()
                reservation.save()

                room.status = "Cleaning"
                room.booking_source = "front_desk"
                room.save(update_fields=["status", "booking_source"])

                RoomHistory.objects.create(
                    room=room,
                    event_type="checkout",
                    guest_name=reservation.guest_name,
                    check_in_date=reservation.check_in_date,
                    check_out_date=reservation.check_out_date,
                    revenue=checkout_revenue,
                    payment_method="Digital Payment",
                    notes=f"Checkout paid via Chapa (Digital) ref {tx_ref}",
                )

                # --- Post General Ledger Journal Entry ---
                try:
                    if checkout_revenue > 0:
                        jv_items = [
                            {
                                "account_code": "1010", # Bank Transfer (Digital)
                                "debit": checkout_revenue,
                                "credit": Decimal("0.00")
                            }
                        ]
                        if is_prepaid:
                            if extras_total > 0:
                                jv_items.append({
                                    "account_code": "1200", # Accounts Receivable
                                    "debit": Decimal("0.00"),
                                    "credit": extras_total
                                })
                        else:
                            if room_total > 0:
                                jv_items.append({
                                    "account_code": "4000", # Room Revenue
                                    "debit": Decimal("0.00"),
                                    "credit": room_total
                                })
                            if extras_total > 0:
                                jv_items.append({
                                    "account_code": "1200", # Accounts Receivable
                                    "debit": Decimal("0.00"),
                                    "credit": extras_total
                                })
                        
                        debit_sum = sum(x["debit"] for x in jv_items)
                        credit_sum = sum(x["credit"] for x in jv_items)
                        diff = debit_sum - credit_sum
                        if diff != 0:
                            target_code = "4000" if room_total > 0 else "1200"
                            for item in jv_items:
                                if item["account_code"] == target_code:
                                    item["credit"] += diff
                                    break

                        if len(jv_items) >= 2:
                            post_journal_entry(
                                description=f"Auto JV: Room Checkout #{reservation.id} digital payment",
                                items=jv_items
                            )
                except Exception as e:
                    print(f"GL Auto-post error for digital checkout: {e}")
            grand_total = checkout_revenue

        return Response({
            "message": "Payment verified successfully!",
            "status": "success",
            "grand_total": float(grand_total),
        })


