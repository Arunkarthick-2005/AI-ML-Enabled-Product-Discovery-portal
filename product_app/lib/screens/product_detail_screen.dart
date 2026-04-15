import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';

class ProductDetailScreen extends StatefulWidget {
  final String productId;

  const ProductDetailScreen({Key? key, required this.productId})
      : super(key: key);

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  late Future<Product> _productFuture;

  @override
  void initState() {
    super.initState();
    _productFuture = ProductService.fetchProductById(widget.productId);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Product Details")),
      body: FutureBuilder<Product>(
        future: _productFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(child: Text(snapshot.error.toString()));
          }

          final product = snapshot.data!;
          return _buildProductUI(product);
        },
      ),
    );
  }

  // -------------------------------------------------
  // PRODUCT UI
  // -------------------------------------------------
  Widget _buildProductUI(Product product) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _imageSection(product.images),

        const SizedBox(height: 16),
        Text(product.title,
            style: const TextStyle(
                fontSize: 20, fontWeight: FontWeight.bold)),

        const SizedBox(height: 8),
        Text("Brand: ${product.brand ?? 'N/A'}"),

        const SizedBox(height: 8),
        Text(
          "₹${product.price?['selling'] ?? 'N/A'}",
          style: const TextStyle(
              fontSize: 18,
              color: Colors.green,
              fontWeight: FontWeight.w600),
        ),

        const Divider(height: 32),

        const Text("Description",
            style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        Text(product.description.isNotEmpty
            ? product.description
            : "No description available"),

        const Divider(height: 32),

        const Text("Specifications",
            style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),

        _buildSpecifications(product.specifications),
      ]),
    );
  }

  // -------------------------------------------------
  // IMAGE SECTION
  // -------------------------------------------------
 Widget _imageSection(List<String> images) {
  if (images.isEmpty) {
    return Container(
      height: 220, // ✅ fixed height
      color: Colors.grey.shade200,
      alignment: Alignment.center,
      child: const Text("No Image"),
    );
  }

  return SizedBox(
    height: 220,
    child: PageView.builder(
      itemCount: images.length,
      itemBuilder: (context, index) {
        return Image.network(
          proxyImageUrl(images[index]),
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) {
            return Container(
              height: 220,
              alignment: Alignment.center,
              child: const Text("Image failed"),
            );
          },
        );
      },
    ),
  );
}

  // -------------------------------------------------
  // SPECIFICATIONS SECTION (ROBUST & SAFE)
  // -------------------------------------------------
  Widget _buildSpecifications(dynamic specifications) {
  // ✅ Case 0: Null
  if (specifications == null) {
    return const Text("No specifications available");
  }

  // ✅ Case 1: Expected structure from backend
  // {
  //   "product_specification": [
  //     {"key": "...", "value": "..."}
  //   ]
  // }
  if (specifications is Map<String, dynamic> &&
      specifications.containsKey('product_specification') &&
      specifications['product_specification'] is List) {
    
    final List specs = specifications['product_specification'];

    if (specs.isEmpty) {
      return const Text("No specifications available");
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: specs.map<Widget>((spec) {
        if (spec is! Map) return const SizedBox();

        final String key = spec['key']?.toString() ?? '';
        final String value = spec['value']?.toString() ?? '';

        if (key.isEmpty && value.isEmpty) {
          return const SizedBox();
        }

        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 4,
                child: Text(
                  key,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 6,
                child: Text(
                  value,
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  // ✅ Case 2: Backend sends specs as plain string (fallback)
  if (specifications is String && specifications.isNotEmpty) {
    return Text(
      specifications,
      style: const TextStyle(fontSize: 14),
    );
  }

  // ✅ Case 3: Any other unexpected format
  return const Text("No specifications available");
}

  // -------------------------------------------------
  // IMAGE PROXY
  // -------------------------------------------------
  String proxyImageUrl(String originalUrl) {
    return "http://localhost:8000/image-proxy?url="
        "${Uri.encodeComponent(originalUrl)}";
  }
}