import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';

/// ✅ Model for Home Screen Collections
class HomeCollections {
  final List<Product> forElectronics;
  final List<Product> forFurniture;
  final List<Product> forClothings;

  HomeCollections({
    required this.forElectronics,
    required this.forFurniture,
    required this.forClothings,
  });

  factory HomeCollections.fromJson(Map<String, dynamic> json) {
    return HomeCollections(
      forElectronics: (json['for_electronics'] as List<dynamic>)
          .map((e) => Product.fromJson(e))
          .toList(),
      forFurniture: (json['for_furniture'] as List<dynamic>)
          .map((e) => Product.fromJson(e))
          .toList(),
      forClothings: (json['for_clothings'] as List<dynamic>)
          .map((e) => Product.fromJson(e))
          .toList(),
    );
  }
}

class ProductService {
  static const String baseUrl = "http://10.0.2.2:8000";

  // -------------------------------------------------------
  // ✅ HOME COLLECTIONS (USED on Home Screen BEFORE SEARCH)
  // -------------------------------------------------------
  static Future<HomeCollections> fetchHomeCollections() async {
    final response = await http.get(
      Uri.parse("$baseUrl/home/collections"),
    );

    if (response.statusCode == 200) {
      final Map<String, dynamic> data = jsonDecode(response.body);
      return HomeCollections.fromJson(data);
    } else {
      throw Exception("Failed to load home collections");
    }
  }

  // -------------------------------------------------------
  // ✅ FETCH SINGLE PRODUCT (Product Detail Page)
  // -------------------------------------------------------
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

  // -------------------------------------------------------
  // ✅ SEARCH PRODUCTS (Search Bar)
  // -------------------------------------------------------
  static Future<List<Product>> searchProducts({
    required String query,
    String? category,
    String? brand,
    int? priceMin,
    int? priceMax,
  }) async {
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
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((e) => Product.fromJson(e)).toList();
    } else {
      throw Exception("Search failed");
    }
  }

  // -------------------------------------------------------
  // ✅ SIMILAR PRODUCTS (Product Detail Page ONLY)
  // -------------------------------------------------------
  static Future<List<Product>> fetchSimilarProducts(
    String productId,
  ) async {
    final response = await http.get(
      Uri.parse("$baseUrl/products/$productId/similar"),
    );

    if (response.statusCode != 200) {
      return [];
    }

    final List<dynamic> data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  }
}