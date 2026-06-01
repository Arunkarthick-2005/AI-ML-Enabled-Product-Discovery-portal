import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/product.dart';
import 'dart:io';

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
  static Future<List<Product>> getProductsByCategory(
      String? l1,
      String? l2,
      String? l3,
      ) async {
    final response = await http.get(
      Uri.parse(
        "$baseUrl/admin/products-by-category"
            "?l1=${l1 ?? ""}&l2=${l2 ?? ""}&l3=${l3 ?? ""}",
      ),
    );

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);
    return data.map((e) => Product.fromJson(e)).toList();
  }
  static Future<List<Product>> getProductsByCategoryPath({
    String? l1,
    String? l2,
    String? l3,
  }) async {

    final queryParams = {
      if (l1 != null) "l1": l1,
      if (l2 != null) "l2": l2,
      if (l3 != null) "l3": l3,
    };

    final uri = Uri.parse("$baseUrl/admin/products-by-category")
        .replace(queryParameters: queryParams);

    final response = await http.get(uri);

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);

    return data.map((e) => Product.fromJson(e)).toList();
  }
  // ✅ DELETE PRODUCT
  static Future<bool> deleteProduct(String pid) async {
    final response = await http.delete(
      Uri.parse("$baseUrl/admin/products/$pid"),
    );

    return response.statusCode == 200;
  }

// ✅ UPDATE PRODUCT
  static Future<bool> updateProduct({
    required String pid,
    required Map<String, dynamic> data,
  }) async {
    final response = await http.put(
      Uri.parse("$baseUrl/admin/products/$pid"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode(data),
    );

    return response.statusCode == 200;
  }
  static Future createProduct(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse("$baseUrl/admin/products"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode(data),
    );

    if (response.statusCode != 200) {
      throw Exception("Failed to create product");
    }

    return jsonDecode(response.body);
  }

  static Future<void> uploadCsv(File file) async {
    try {
      print("📤 Uploading file: ${file.path}");

      var request = http.MultipartRequest(
        'POST',
        Uri.parse("$baseUrl/admin/products/upload-csv"),
      );

      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          file.path,
        ),
      );

      var response = await request.send();

      print("📡 Response status: ${response.statusCode}");

      final responseBody = await response.stream.bytesToString();
      print("📡 Response body: $responseBody");

      if (response.statusCode != 200) {
        throw Exception("Server error: ${response.statusCode}");
      }

    } catch (e) {
      print("❌ Service error: $e");
      rethrow;
    }
  }


}