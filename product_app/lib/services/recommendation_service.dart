import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';

class RecommendationService {
  static const String baseUrl = "http://10.0.2.2:8000";

  // =================================================
  // GENERIC INTERACTION LOGGER
  // =================================================
  static Future<void> logInteraction({
    required String userId,
    required String productId,
    required String eventType, // view | search_view | similar_view
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
  // SEARCH RESULT CLICK
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
    String userId,
  ) async {
    final response = await http.get(
      Uri.parse("$baseUrl/recommendations/user/$userId"),
    );

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  }

  // =================================================
  // ✅ TRENDING PRODUCTS PER CATEGORY (DYNAMIC)
  // =================================================
  static Future<Map<String, List<Product>>> getTrendingByCategory({
    int topNPerCategory = 3,
  }) async {
    final response = await http.get(
      Uri.parse(
        "$baseUrl/products/trending-by-category"
        "?top_n_per_category=$topNPerCategory",
      ),
    );

    if (response.statusCode != 200) {
      return {};
    }

    final Map<String, dynamic> data = jsonDecode(response.body);

    return data.map(
      (category, products) => MapEntry(
        category,
        (products as List)
            .map((p) => Product.fromJson(p))
            .toList(),
      ),
    );
  }
  static Future<List<Product>> getNextBestAlternatives({
    required String productId,
    String query = "",
    int limit = 5,
  }) async {
    final uri = Uri.parse(
        "$baseUrl/products/$productId/alternatives"
            "?query=${Uri.encodeComponent(query)}"
            "&limit=$limit");

    final response = await http.get(uri);

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  }
}