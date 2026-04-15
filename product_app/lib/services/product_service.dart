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
static Future<List<Product>> searchProducts({
  required String query,
  String? category,
  String? brand ,
  int? priceMin ,
  int? priceMax,
}) async {
  // Build query parameters
  final Map<String, String> params = {
    'q': query,
  };

  if (category != null && category.isNotEmpty) {
    params['category'] = category;
  }

  if (brand != null && brand.isNotEmpty) {
    params['brand'] = brand;
  }

  if (priceMin != null) {
    params['price_min'] = priceMin.toString();
  }

  if (priceMax != null) {
    params['price_max'] = priceMax.toString();
  }

  final uri = Uri.parse("$baseUrl/products/search")
      .replace(queryParameters: params);

  final response = await http.get(uri);

  if (response.statusCode == 200) {
    final List data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  } else {
    throw Exception("Search failed");
  }
}
}