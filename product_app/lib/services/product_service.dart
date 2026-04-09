import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';

class ProductService {
  static const String baseUrl = "http://localhost:8000";

  /// ✅ Fetch single product by ID (USED by ProductDetailScreen)
  static Future<Product> fetchProductById(String productId) async {
    final response = await http.get(
      Uri.parse("$baseUrl/products/$productId"),
    );

    if (response.statusCode == 200) {
      return Product.fromJson(jsonDecode(response.body));
    } else {
      throw Exception("Failed to load product");
    }
  }

  /// ✅ Search products (USED by search bar)
  static Future<List<Product>> searchProducts(String query) async {
    final response = await http.get(
      Uri.parse("$baseUrl/products/search?q=${Uri.encodeComponent(query)}"),
    );

    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.map((e) => Product.fromJson(e)).toList();
    } else {
      throw Exception("Search failed");
    }
  }
}