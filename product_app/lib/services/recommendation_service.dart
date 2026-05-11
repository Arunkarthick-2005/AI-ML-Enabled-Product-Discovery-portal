import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';

class RecommendationService {
  static const String baseUrl = "http://localhost:8000";

  // =================================================
  // GENERIC INTERACTION LOGGER
  // =================================================
  static Future<void> logInteraction({
    required String userId,
    required String productId,
    required String eventType, // view | search_view
    String source = "unknown",
  }) async {
    await http.post(
      Uri.parse("$baseUrl/recommendations/log-interaction"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "user_id": userId,
        "product_id": productId,
        "event_type": eventType,
        "source": source,
      }),
    );
  }

  // =================================================
  // PRODUCT DETAIL VIEW
  // =================================================
  static Future<void> logView({
    required String userId,
    required String productId,
  }) async {
    return logInteraction(
      userId: userId,
      productId: productId,
      eventType: "view",
      source: "detail_page",
    );
  }

  // =================================================
  // SEARCH RESULT CLICK (✅ NEW)
  // =================================================
  static Future<void> logSearchView({
    required String userId,
    required String productId,
  }) async {
    return logInteraction(
      userId: userId,
      productId: productId,
      eventType: "search_view",
      source: "search_results",
    );
  }

  // =================================================
  // USER-SPECIFIC RECOMMENDATIONS
  // =================================================
  static Future<List<Product>> getUserRecommendations(
      String userId) async {
    final response = await http.get(
      Uri.parse("$baseUrl/recommendations/user/$userId"),
    );

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  }
}