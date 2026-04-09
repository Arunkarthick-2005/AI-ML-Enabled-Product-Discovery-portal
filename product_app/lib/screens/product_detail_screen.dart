import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import '../utils/category_utils.dart';

class ProductDetailScreen extends StatefulWidget {
  final String productId;

  const ProductDetailScreen({super.key, required this.productId});

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
      appBar: AppBar(
        title: const Text("Product Details"),
      ),
      body: FutureBuilder<Product>(
        future: _productFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Text(snapshot.error.toString()),
            );
          }

          final product = snapshot.data!;
          return _buildProductUI(product);
        },
      ),
    );
  }

  Widget _buildProductUI(Product product) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _imageSection(product.images),

          const SizedBox(height: 16),

          Text(
            product.title,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),

          const SizedBox(height: 8),
          Text("Brand: ${product.brand}"),

          const SizedBox(height: 8),
          Text(
            "₹${product.price['selling']}",
            style: const TextStyle(
              fontSize: 18,
              color: Colors.green,
              fontWeight: FontWeight.w600,
            ),
          ),

          const SizedBox(height: 8),

          // ✅ Category display (no nulls)
          Text(
            formatCategory(product.category),
            style: const TextStyle(fontSize: 14),
          ),

          const Divider(height: 32),

          const Text(
            "Description",
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          Text(product.description),

          const Divider(height: 32),

          const Text(
            "Specifications",
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),

          // ✅ Clean specification display
          _buildSpecifications(product.specifications),
        ],
      ),
    );
  }

  // -------------------------------------------------
  // IMAGE SECTION
  // -------------------------------------------------
  Widget _imageSection(List images) {
    if (images.isEmpty) {
      return Container(
        height: 200,
        color: Colors.grey.shade200,
        child: const Center(child: Text("No Image")),
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
            errorBuilder: (context, error, stackTrace) {
              return const Center(
                child: Text("Image failed to load"),
              );
            },
          );
        },
      ),
    );
  }

  // -------------------------------------------------
  // SPECIFICATIONS SECTION (KEY : VALUE)
  // -------------------------------------------------
  Widget _buildSpecifications(dynamic specifications) {
    if (specifications == null ||
        specifications is! Map ||
        !specifications.containsKey('product_specification')) {
      return const Text("No specifications available");
    }

    final List specs = specifications['product_specification'];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: specs.map<Widget>((spec) {
        final key = spec['key'];
        final value = spec['value'];

        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Text(
            "$key: $value",
            style: const TextStyle(fontSize: 14),
          ),
        );
      }).toList(),
    );
  }

  // -------------------------------------------------
  // IMAGE PROXY
  // -------------------------------------------------
  String proxyImageUrl(String originalUrl) {
    return "http://localhost:8000/image-proxy?url="
        "${Uri.encodeComponent(originalUrl)}";
  }
}