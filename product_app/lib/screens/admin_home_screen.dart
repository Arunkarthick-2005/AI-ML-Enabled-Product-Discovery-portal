import 'package:flutter/material.dart';
import 'login_screen.dart';
import '../services/admin_service.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import 'admin_product_detail_view.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';


enum AdminViewState {
  home,
  categories,
  products,
  detail,
  edit,
  add,
  uploadCsv
}

class AdminHomeScreen extends StatefulWidget {
  const AdminHomeScreen({super.key});

  @override
  State<AdminHomeScreen> createState() => _AdminHomeScreenState();
}

class _AdminHomeScreenState extends State<AdminHomeScreen> {

  AdminViewState _viewState = AdminViewState.home;

  List<CategoryNode> _allCategories = [];
  Future<List<Product>>? _productFuture;

  String _searchQuery = "";
  String? _selectedProductId;
  String? _currentCategoryName;
  Product? _editingProduct;

  final _title = TextEditingController();
  final _brand = TextEditingController();
  final _price = TextEditingController();
  final _retailPrice = TextEditingController(); // ✅ NEW
  final _desc = TextEditingController();
  final _l1 = TextEditingController();
  final _l2 = TextEditingController();
  final _l3 = TextEditingController();
  final _specs = TextEditingController();
  final _images = TextEditingController();
  final _csvPath = TextEditingController();
  String? _selectedL1;
  String? _selectedL2;
  String? _selectedL3;


  // ✅ SEARCH
  List<CategoryNode> _filteredCategories() {
    if (_searchQuery.isEmpty) return _allCategories;

    return _allCategories.where((c) {
      return c.name.toLowerCase().contains(_searchQuery.toLowerCase());
    }).toList();
  }

  // ✅ LOGOUT
  void _logout() {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
          (_) => false,
    );
  }

  void _loadProductsByPath({String? l1, String? l2, String? l3}) {
    setState(() {
      _viewState = AdminViewState.products;

      // ✅ ✅ CRITICAL FIX (STORE VALUES)
      _selectedL1 = l1;
      _selectedL2 = l2;
      _selectedL3 = l3;

      _currentCategoryName = "$l1 > $l2 > $l3";

      _productFuture =
          ProductService.getProductsByCategoryPath(
            l1: l1,
            l2: l2,
            l3: l3,
          );
    });
  }

  Future<bool> _requestStoragePermission() async {

    if (Platform.isAndroid) {

      if (await Permission.manageExternalStorage.isGranted) {
        print("✅ Already granted");
        return true;
      }

      var status = await Permission.manageExternalStorage.request();

      if (status.isGranted) {
        print("✅ Storage permission granted");
        return true;
      } else {
        print("❌ Storage permission denied");
        return false;
      }
    }

    return true;
  }


  // ✅ LOAD CATEGORIES
  void _loadCategories() async {
    setState(() => _viewState = AdminViewState.categories);
    final data = await AdminService.getCategoryTree();

    setState(() {
      _allCategories = data;
    });
  }

  void _startUploadCsv() {
    setState(() {
      _viewState = AdminViewState.uploadCsv;
    });
  }

  void _startAddProduct() {

    // ✅ clear all fields
    _title.clear();
    _brand.clear();
    _price.clear();
    _desc.clear();
    _l1.clear();
    _l2.clear();
    _l3.clear();
    _specs.clear();

    setState(() {
      _viewState = AdminViewState.add;
    });
  }

  // ✅ LOAD PRODUCTS
  /*void _loadProducts(String categoryName) {
    setState(() {
      _currentCategoryName = categoryName;
      _viewState = AdminViewState.products;

      _productFuture =
          ProductService.getProductsByCategoryName(categoryName);
    });
  }*/
  void _uploadCsvFromPath() async {

    final path = _csvPath.text.trim();

    // ✅ REQUEST PERMISSION FIRST
    bool hasPermission = await _requestStoragePermission();

    if (!hasPermission) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Storage permission required ❌")),
      );
      return;
    }

    final file = File(path);

    print("📂 Exists: ${file.existsSync()}");

    if (!file.existsSync()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("File not found ❌")),
      );
      return;
    }

    try {
      await ProductService.uploadCsv(file);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("CSV uploaded ✅")),
      );

    } catch (e) {
      print("Upload error: $e");
    }
  }


  void _createProduct() async {

    // ✅ SPLIT IMAGES
    final images = _images.text
        .split(",")
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();

    // ✅ SPLIT SPECS
    List<Map<String, String>> specs = [];

    final rawSpecs = _specs.text.split(",");
    for (var item in rawSpecs) {
      if (item.contains(":")) {
        final parts = item.split(":");
        specs.add({
          "key": parts[0].trim(),
          "value": parts[1].trim(),
        });
      }
    }

    try {
      final response = await ProductService.createProduct({
        "title": _title.text,
        "brand": _brand.text,
        "description": _desc.text,

        "price": {
          "selling": int.tryParse(_price.text) ?? 0,
          "retail": int.tryParse(_retailPrice.text) ?? 0,
        },

        "category": {
          "level_1": _l1.text,
          "level_2": _l2.text.isEmpty ? null : _l2.text,
          "level_3": _l3.text.isEmpty ? null : _l3.text,
        },

        "images": images,

        "specifications": specs
      });

      // ✅ BACK TO HOME
      setState(() {
        _viewState = AdminViewState.home;
      });

    } catch (e) {
      print("Create Product Error: $e");
    }
  }
  // ✅ OPEN DETAIL
  void _openProduct(String pid) {
    setState(() {
      _selectedProductId = pid;
      _viewState = AdminViewState.detail;
    });
  }

  // ✅ BACK
  void _handleBack() {
    setState(() {
      if (_viewState == AdminViewState.edit) {
        _viewState = AdminViewState.products;  // ✅ NEW
      } else if (_viewState == AdminViewState.detail) {
        _viewState = AdminViewState.products;
      } else if (_viewState == AdminViewState.products) {
        _loadCategories();
      } else if (_viewState == AdminViewState.categories) {
        _viewState = AdminViewState.home;
      }
      else if (_viewState == AdminViewState.add) {
        _viewState = AdminViewState.home;
      }
      else if (_viewState == AdminViewState.uploadCsv) {
        _viewState = AdminViewState.home;
      }


    });
  }

  // =============================
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,

      appBar: AppBar(
        backgroundColor: Colors.blue,
        leading: _viewState != AdminViewState.home
            ? IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: _handleBack,
        )
            : null,
        title: const Text("Admin Dashboard",
            style: TextStyle(color: Colors.white)),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white),
            onPressed: _logout,
          )
        ],
      ),

      body: _buildBody(),
    );
  }

  // =============================
  Widget _buildBody() {
    switch (_viewState) {

      case AdminViewState.uploadCsv:
        return _buildUploadCsvView(); // ✅ NEW

      case AdminViewState.edit:
        return _buildEditView();

      case AdminViewState.home:
        return _buildHome();

      case AdminViewState.add:
        return _buildAddView();

      case AdminViewState.categories:
        return _buildCategoryTree();

      case AdminViewState.products:
        return _buildProducts();

      case AdminViewState.detail:
        return AdminProductDetailView(
          productId: _selectedProductId!,
        );
    }
  }



  // =============================
  Widget _buildHome() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // ✅ ✅ CSV INGESTION (UPDATED ✅)
            _buildButton(
              "Product Ingestion (CSV Upload)",
              Icons.upload_file,  // ✅ better icon
              _startUploadCsv,
              Colors.lightBlue,
            ),
            const SizedBox(height: 20),

            // ✅ CATEGORY
            _buildButton(
              "Category Management",
              Icons.category,
              _loadCategories,
              Colors.green,
            ),
          ],
        ),
      ),
    );
  }


  Widget _buildAddView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          // ✅ IMAGE (comma separated URLs)
          _field("Image URLs (comma separated)", _images,maxLines: 2),

          _field("Title", _title),
          _field("Brand", _brand),

          // ✅ PRICE
          _field("Selling Price", _price),
          _field("Retail Price", _retailPrice),

          _field("Description", _desc, maxLines: 3),

          const Divider(),

          // ✅ CATEGORY
          _field("Level 1", _l1),
          _field("Level 2", _l2),
          _field("Level 3", _l3),

          const Divider(),

          // ✅ SPECIFICATIONS
          _field(
            "Specifications (key:value,comma separated)",
            _specs,
            maxLines: 3,
          ),

          const SizedBox(height: 20),

          SizedBox(
            width: double.infinity,
            height: 45,
            child: ElevatedButton(
              onPressed: _createProduct,
              child: const Text("Create Product"),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadCsvView() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          const Text(
            "Upload CSV (Enter File Path)",
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),

          const SizedBox(height: 20),

          _field("CSV File Path", _csvPath),

          const SizedBox(height: 20),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _uploadCsvFromPath,
              child: const Text("Upload CSV"),
            ),
          ),
        ],
      ),
    );
  }

  // =============================
  Widget _buildCategoryTree() {
    if (_allCategories.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    final list = _filteredCategories();

    return Column(
      children: [

        // ✅ SEARCH
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              hintText: "Search category...",
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
            onChanged: (v) => setState(() => _searchQuery = v),
          ),
        ),

        Expanded(
          child: list.isEmpty
              ? const Center(child: Text("No categories"))
              : ListView(children: list.map(_tree).toList()),
        ),
      ],
    );
  }

  Widget _tree(CategoryNode n, {String? l1, String? l2}) {

    String? currentL1 = l1;
    String? currentL2 = l2;
    String? currentL3;

    // ✅ determine hierarchy
    if (l1 == null) {
      currentL1 = n.name;      // Level 1
    } else if (l2 == null) {
      currentL2 = n.name;      // Level 2
    } else {
      currentL3 = n.name;      // Level 3
    }

    bool isLeaf = n.children == null || n.children!.isEmpty;

    // ✅ ✅ LEAF NODE → LOAD PRODUCTS
    if (isLeaf) {
      return ListTile(
        title: Text(n.name),
        trailing: const Icon(Icons.arrow_forward),

        onTap: () => _loadProductsByPath(
          l1: currentL1,
          l2: currentL2,
          l3: currentL3,
        ),
      );
    }

    // ✅ ✅ NON-LEAF → ONLY EXPAND (NO PRODUCT LOAD)
    return ExpansionTile(
      title: Text(n.name),
      children: n.children!.map((child) {
        return _tree(
          child,
          l1: currentL1,
          l2: currentL2,
        );
      }).toList(),
    );
  }

  // =============================
  Widget _buildProducts() {
    return FutureBuilder<List<Product>>(
      future: _productFuture,
      builder: (_, snap) {
        if (!snap.hasData) {
          return const Center(child: CircularProgressIndicator());
        }

        final list = snap.data!;

        if (list.isEmpty) {
          return const Center(child: Text("No products"));
        }

        return GridView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: list.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            childAspectRatio: 0.78,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
          ),
            itemBuilder: (_, i) {
              final p = list[i];

              return InkWell(
                onTap: () => _openProduct(p.pid), // ✅ FIXED
                child: _card(p),
              );
            }
        );
      },
    );
  }

  // =============================
// ✅ INLINE EDIT VIEW (MISSING)
  Widget _buildEditView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          _field("Title", _title),
          _field("Brand", _brand),
          _field("Price", _price),

          _field("Description", _desc, maxLines: 3),

          const Divider(),

          _field("Level 1", _l1),
          _field("Level 2", _l2),
          _field("Level 3", _l3),

          const Divider(),

          _field("Specifications", _specs, maxLines: 4),

          const SizedBox(height: 20),

          SizedBox(
            width: double.infinity,
            height: 45,
            child: ElevatedButton(
              onPressed: _updateProduct,
              child: const Text("Update Product"),
            ),
          ),
        ],
      ),
    );
  }

  // =============================
  Widget _card(Product p) {
    final img = p.images.isNotEmpty ? p.images.first : null;
    final price = p.price?["selling"];
    final imageUrl = img != null
        ? "http://10.0.2.2:8000/image-proxy?url=${Uri.encodeComponent(img)}"
        : null;
    return Card(
      color: Colors.white,
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // ✅ IMAGE
        SizedBox(
        height: 90,
        width: double.infinity,
        child: imageUrl != null
            ? ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image.network(
            imageUrl,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => const Icon(Icons.broken_image),
          ),
        )
            : const Icon(Icons.image),
      ),

            const SizedBox(height: 6),

            // ✅ TITLE
            Text(
              p.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),

            const SizedBox(height: 2),

            // ✅ BRAND
            Text(
              p.brand ?? "",
              style: TextStyle(
                fontSize: 10,
                color: Colors.grey.shade700,
              ),
            ),

            const SizedBox(height: 6),

            // ✅ PRICE
            if (price != null)
              Text(
                "₹$price",
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),

            const SizedBox(height: 6),

            // ✅ ✅ COLORED ACTION BUTTONS
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [

                // ✏️ EDIT BUTTON
                GestureDetector(
                  onTap: () => _startEdit(p),
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.blue.shade100,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.edit,
                      size: 16,
                      color: Colors.blue.shade700,
                    ),
                  ),
                ),

                // 🗑 DELETE BUTTON
                GestureDetector(
                  onTap: () => _delete(p.pid),
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.red.shade100,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.delete,
                      size: 16,
                      color: Colors.red.shade700,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // =============================
  // ✅ FULL UPDATE ALL FIELDS
  void _startEdit(Product p) {

    _editingProduct = p;

    _title.text = p.title;
    _brand.text = p.brand ?? "";
    _price.text = p.price?["selling"]?.toString() ?? "";
    _retailPrice.text = p.price?["retail"]?.toString() ?? "";
    _desc.text = p.description ?? "";

    _l1.text = p.category?["level_1"] ?? "";
    _l2.text = p.category?["level_2"] ?? "";
    _l3.text = p.category?["level_3"] ?? "";

    _specs.text = p.specifications?.toString() ?? "";

    setState(() {
      _viewState = AdminViewState.edit;
    });
  }

  void _updateProduct() async {

    if (_editingProduct == null) return;

    await ProductService.updateProduct(
      pid: _editingProduct!.pid,
      data: {
        "title": _title.text,
        "brand": _brand.text,
        "description": _desc.text,
        "price": {
          "selling": int.tryParse(_price.text) ?? 0,
          "retail": int.tryParse(_retailPrice.text) ?? 0,
        },
        "category": {
          "level_1": _l1.text,
          "level_2": _l2.text.isEmpty ? null : _l2.text,
          "level_3": _l3.text.isEmpty ? null : _l3.text,
        },
        "specifications": _specs.text,
      },
    );

    setState(() {
      _viewState = AdminViewState.products;

      _productFuture =
          ProductService.getProductsByCategoryPath(
            l1: _selectedL1,
            l2: _selectedL2,
            l3: _selectedL3,
          );
    });
  }

  // =============================
  void _delete(String pid) async {

    await ProductService.deleteProduct(pid);

    setState(() {
      _productFuture =
          ProductService.getProductsByCategoryPath(
            l1: _selectedL1,
            l2: _selectedL2,
            l3: _selectedL3,
          );
    });
  }

  // =============================
  Widget _field(String label, TextEditingController c,
      {int maxLines = 1}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: TextField(
        controller: c,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          border:
          OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
    );
  }

  Widget _buildButton(
      String t, IconData i, VoidCallback f, Color c) {
    return SizedBox(
      width: double.infinity,
      height: 60,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(backgroundColor: c),
        onPressed: f,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(i),
            const SizedBox(width: 10),
            Text(t),
          ],
        ),
      ),
    );
  }
}