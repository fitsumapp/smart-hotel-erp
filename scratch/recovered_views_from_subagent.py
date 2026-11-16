

class StocktakeSessionViewSet(viewsets.ModelViewSet):
    queryset = StocktakeSession.objects.all().select_related(
        "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
    ).prefetch_related("items__item")
    serializer_class = StocktakeSessionSerializer
    permission_classes = [IsInventoryManager]

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location") or request.data.get("location_id")
        category_id = request.data.get("category") or request.data.get("category_id")
        counting_mode = request.data.get("counting_mode", "blind")
        title = request.data.get("title")

        if not location_id:
            return Response({"error": "location is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = create_stocktake_session(
                location=location_id,
                category=category_id,
                counting_mode=counting_mode,
                title=title,
                created_by=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="record-counts")
    def record_counts(self, request, pk=None):
        counts = request.data.get("counts") or request.data.get("items") or request.data.get("counts_data")
        if counts is None and isinstance(request.data, list):
            counts = request.data

        if not counts:
            return Response({"error": "counts data is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = record_counts(
                session_id=pk,
                counts_data=counts,
                user=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="request-recount")
    def request_recount(self, request, pk=None):
        item_ids = request.data.get("item_ids") or request.data.get("items")
        reason = request.data.get("reason", "")
        if not item_ids:
            return Response({"error": "item_ids is required for recount."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = request_recount(
                session_id=pk,
                item_ids=item_ids,
                reason=reason,
                supervisor=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="submit-recount")
    def submit_recount(self, request, pk=None):
        recounts = (
            request.data.get("recounts")
            or request.data.get("recount_data")
            or request.data.get("counts")
            or request.data.get("items")
        )
        if recounts is None and isinstance(request.data, list):
            recounts = request.data

        if not recounts:
            return Response({"error": "recount data is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = submit_recount(
                session_id=pk,
                recount_data=recounts,
                user=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        notes = request.data.get("notes", "")
        try:
            session = approve_stocktake_session(
                session_id=pk,
                supervisor=request.user,
                notes=notes,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        reason = request.data.get("reason", "")
        try:
            session = cancel_stocktake_session(
                session_id=pk,
                user=request.user,
                reason=reason,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
