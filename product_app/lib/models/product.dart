class Product {
  final String pid;
  final String title;
  final String brand;
  final Map<String, dynamic> price;
  final Map<String, dynamic> category;
  final String description;
  final List<String> images;         // ✅ FIXED
  final dynamic specifications;

  Product({
    required this.pid,
    required this.title,
    required this.brand,
    required this.price,
    required this.category,
    required this.description,
    required this.images,
    required this.specifications,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      pid: json['pid'] ?? '',
      title: json['title'] ?? '',
      brand: json['brand'] ?? '',
      price: Map<String, dynamic>.from(json['price'] ?? {}),
      category: Map<String, dynamic>.from(json['category'] ?? {}),
      description: json['description'] ?? '',
      images: json['images'] != null
          ? List<String>.from(json['images'])
          : [],                           // ✅ FIXED
      specifications: json['specifications'],
    );
  }
}
