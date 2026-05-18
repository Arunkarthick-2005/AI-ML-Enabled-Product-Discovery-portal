import 'dart:convert';
import 'package:http/http.dart' as http;

class CopilotService {
  static const String baseUrl = "http://10.0.2.2:8000";

  // =================================================
  // ✅ GENERIC COPILOT (UNCHANGED)
  // =================================================
  static Future<String> askCopilot(String query) async {
    final response = await http.post(
      Uri.parse("$baseUrl/copilot/chat"),
      headers: {
        "Content-Type": "application/json",
      },
      body: jsonEncode({
        "query": query,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception("Generic Copilot failed");
    }

    final data = jsonDecode(response.body);
    return data["answer"] ?? "No response available.";
  }

  // =================================================
  // ✅ PRODUCT‑SCOPED COPILOT (UPDATED ENDPOINT)
  // =================================================
  static Future<String> askCopilotForProduct({
    required String question,
    required String productId,
  }) async {
    final response = await http.post(
      // ✅ NOTE THE ENDPOINT CHANGE HERE
      Uri.parse("$baseUrl/copilot/chat/product"),
      headers: {
        "Content-Type": "application/json",
      },
      body: jsonEncode({
        "question": question,
        "product_id": productId,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception("Product Copilot failed");
    }

    final data = jsonDecode(response.body);
    return data["answer"] ?? "No response available.";
  }
}
