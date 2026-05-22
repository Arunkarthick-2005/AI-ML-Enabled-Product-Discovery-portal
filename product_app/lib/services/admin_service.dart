import 'dart:convert';
import 'package:http/http.dart' as http;


class CategoryNode {
  final String name;
  final List<CategoryNode>? children;

  CategoryNode({
    required this.name,
    this.children,
  });

  factory CategoryNode.fromJson(Map<String, dynamic> json) {
    return CategoryNode(
      name: json["name"],
      children: json["children"] != null
          ? (json["children"] as List)
          .map((e) => CategoryNode.fromJson(e))
          .toList()
          : null,
    );
  }
}

class AdminService {
  static const String baseUrl = "http://10.0.2.2:8000";

  // ✅ GET CATEGORY TREE
  static Future<List<CategoryNode>> getCategoryTree() async {
    final response = await http.get(
      Uri.parse("$baseUrl/admin/categories-tree"),
    );

    if (response.statusCode != 200) return [];

    final List data = jsonDecode(response.body);

    return data.map((e) => CategoryNode.fromJson(e)).toList();
  }

}