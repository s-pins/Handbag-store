from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from .models import Handbag, Order, OrderItem, Category # Import Order and OrderItem, Category
from .mpesa import MpesaClient
from .forms import CustomUserCreationForm, CustomAuthenticationForm # Import custom forms
from django.contrib import messages # Import messages for feedback to user
import json # Import json for parsing M-Pesa callback
from django.http import HttpResponse # Import HttpResponse for callback response
import logging # Import logging
from django.contrib.auth.decorators import login_required # Import login_required
from django.db.models import Q # Import Q object for complex queries

# Get an instance of a logger
logger = logging.getLogger(__name__)

# 1. The Home Page / Catalog
def catalog(request):
    bags = Handbag.objects.all()
    query = request.GET.get('q')
    category_id = request.GET.get('category')
    
    if query:
        bags = bags.filter(Q(name__icontains=query) | Q(description__icontains=query))
        
    if category_id:
        bags = bags.filter(category__id=category_id)
        
    categories = Category.objects.all() # Get all categories for filtering options
    category_names = {category.id: category.name for category in categories} # Dictionary for category names

    context = {
        'bags': bags,
        'categories': categories,
        'category_names': category_names, # Pass the dictionary to context
        'selected_category': int(category_id) if category_id else None,
        'query': query
    }
    return render(request, 'catalog.html', context)

# 2. Product Detail Page
def bag_detail(request, bag_id):
    bag = get_object_or_404(Handbag, id=bag_id)
    return render(request, 'bag_detail.html', {'bag': bag})

# 3. Add to Cart Logic (using Sessions)
def add_to_cart(request, bag_id):
    bag = get_object_or_404(Handbag, id=bag_id) # Ensure handbag exists
    cart = request.session.get('cart', {})
    cart[str(bag_id)] = cart.get(str(bag_id), 0) + 1
    request.session['cart'] = cart
    messages.success(request, f"'{bag.name}' added to bag!")
    return redirect('catalog')

# 4. The Shopping Cart View
def view_cart(request):
    cart = request.session.get('cart', {})
    items = []
    total = 0
    for bag_id, quantity in cart.items():
        bag = get_object_or_404(Handbag, id=bag_id)
        subtotal = bag.price * quantity
        items.append({'bag': bag, 'quantity': quantity, 'subtotal': subtotal})
        total += subtotal
    return render(request, 'cart.html', {'items': items, 'total': total})

# 5. The Checkout View (This is what was missing!) - Will be implemented later
def checkout(request, bag_id=None):
    return render(request, 'checkout.html')

# 6. Clear cart functionality
def clear_cart(request):
    if 'cart' in request.session:
        del request.session['cart']
        messages.info(request, "Your bag has been cleared.")
    return redirect('view_cart')

# 7. Initiate payment - Now creates a pending order
def initiate_payment(request):
    if request.method == "POST":
        phone_number = request.POST.get('phone')
        total_amount = float(request.POST.get('amount')) # Ensure amount is float for decimal field

        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "Your cart is empty. Please add items before proceeding to checkout.")
            return redirect('view_cart')

        # 1. Create a Pending Order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            total_amount=total_amount,
            status='Pending',
            phone_number=phone_number
        )

        # 2. Add items to the Order
        for bag_id, quantity in cart.items():
            bag = get_object_or_404(Handbag, id=bag_id)
            OrderItem.objects.create(
                order=order,
                handbag=bag,
                quantity=quantity,
                price=bag.price # Store price at the time of order
            )

        # 3. Trigger STK Push
        cl = MpesaClient()
        # Use a unique account reference for M-Pesa, e.g., order ID
        account_reference = f"Order_{order.id}"
        transaction_desc = f"Payment for Order {order.id} from The Handbag Store"

        response = cl.stk_push(phone_number, total_amount, account_reference, transaction_desc)
        
        if response.get('ResponseCode') == '0':
            # Store the M-Pesa CheckoutRequestID for callback reconciliation
            order.mpesa_checkout_request_id = response.get('CheckoutRequestID') # Add this field to Order model later
            order.save()

            messages.success(request, 'Check your phone for the M-Pesa prompt to complete your payment!')
            # Redirect to a page indicating pending payment or back to cart with status
            return redirect('success') # Using generic success for now, will create a dedicated pending page
        else:
            # If STK push fails, delete the created order to avoid orphan records
            order.delete() 
            messages.error(request, f"M-Pesa payment initiation failed: {response.get('CustomerMessage', 'Unknown error')}. Please try again.")
            return redirect('view_cart')
    return redirect('view_cart') # Should not be accessed directly via GET

# 8. User Registration View
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Log the user in immediately after registration
            messages.success(request, f"Account created for {user.username}!")
            return redirect('catalog') # Redirect to catalog after successful registration
        else:
            # Add error messages if the form is invalid
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

# 9. User Login View
def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username') # This will be 'email' since USERNAME_FIELD is email
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('catalog') # Redirect to a dashboard or catalog page
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

# 10. User Logout View
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('catalog') # Redirect to catalog or login page after logout


# 11. Simple Success View
def success_view(request):
    return render(request, 'success.html')

# 12. M-Pesa STK Push Callback View
def stk_callback(request):
    if request.method == 'POST':
        try:
            mpesa_response = json.loads(request.body)
            logger.info(f"M-Pesa Callback Received: {mpesa_response}")

            # Safaricom sends an array in 'stkCallback'
            callback_data = mpesa_response.get('Body', {}).get('stkCallback', {})
            checkout_request_id = callback_data.get('CheckoutRequestID')
            result_code = callback_data.get('ResultCode')
            result_desc = callback_data.get('ResultDesc')
            merchant_request_id = callback_data.get('MerchantRequestID')

            # Find the corresponding Order
            try:
                order = Order.objects.get(mpesa_checkout_request_id=checkout_request_id)
            except Order.DoesNotExist:
                logger.error(f"Order not found for CheckoutRequestID: {checkout_request_id}")
                return HttpResponse(json.dumps({'ResultCode': 1, 'ResultDesc': 'Order not found'}), content_type="application/json")

            if result_code == 0: # Successful transaction
                items_paid = callback_data.get('CallbackMetadata', {}).get('Item', [])
                mpesa_receipt_number = None
                amount_paid = None
                phone_number = None

                for item in items_paid:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        mpesa_receipt_number = item.get('Value')
                    elif item.get('Name') == 'Amount':
                        amount_paid = item.get('Value')
                    elif item.get('Name') == 'PhoneNumber':
                        phone_number = item.get('Value')

                order.status = 'Paid'
                order.mpesa_transaction_id = mpesa_receipt_number
                order.save()

                # Decrement stock for each item in the order
                for order_item in order.orderitem_set.all():
                    handbag = order_item.handbag
                    if handbag.stock_count >= order_item.quantity:
                        handbag.stock_count -= order_item.quantity
                        handbag.save()
                    else:
                        logger.warning(f"Insufficient stock for {handbag.name} (ID: {handbag.id}) for order {order.id}. Ordered: {order_item.quantity}, Available: {handbag.stock_count}")
                        # Optionally, handle out-of-stock situation (e.g., mark order as partially fulfilled, notify admin)
                
                # Clear cart from session for authenticated user
                if request.user.is_authenticated and 'cart' in request.session:
                     del request.session['cart']

                logger.info(f"Order {order.id} successfully paid. MpesaReceiptNumber: {mpesa_receipt_number}")
                return HttpResponse(json.dumps({'ResultCode': 0, 'ResultDesc': 'Callback received successfully'}), content_type="application/json")
            else:
                # Failed transaction
                order.status = 'Cancelled' # Or 'Failed'
                order.save()
                logger.warning(f"M-Pesa transaction failed for Order {order.id}. ResultCode: {result_code}, ResultDesc: {result_desc}")
                return HttpResponse(json.dumps({'ResultCode': 1, 'ResultDesc': 'Transaction failed'}), content_type="application/json")

        except json.JSONDecodeError:
            logger.error("M-Pesa callback: Invalid JSON received.")
            return HttpResponse(json.dumps({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'}), content_type="application/json")
        except Exception as e:
            logger.error(f"Error processing M-Pesa callback: {e}", exc_info=True)
            return HttpResponse(json.dumps({'ResultCode': 1, 'ResultDesc': 'Internal Server Error'}), content_type="application/json")
    return HttpResponse(json.dumps({'ResultCode': 1, 'ResultDesc': 'Invalid request method'}), content_type="application/json", status=405)


# 13. User Profile View
@login_required
def profile_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'user': request.user,
        'orders': orders
    }
    return render(request, 'profile.html', context)


# 14. Download Invoice View
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from django.db.models import Sum

@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Security check: Ensure the user requesting the invoice owns the order
    if order.user != request.user:
        messages.error(request, "You are not authorized to view this invoice.")
        return redirect('profile') # Redirect to profile page or show a 403 error

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    # Set up basic font and size
    p.setFont("Helvetica-Bold", 24)
    p.drawString(inch, height - inch, "INVOICE")

    p.setFont("Helvetica", 10)
    p.drawString(inch, height - inch - 0.3 * inch, "The Handbag Store")
    p.drawString(inch, height - inch - 0.5 * inch, "123 Fashion Lane, Style City, SC 12345")
    p.drawString(inch, height - inch - 0.7 * inch, "Email: support@handbagstore.com | Phone: (123) 456-7890")

    # Order details
    p.setFont("Helvetica-Bold", 12)
    p.drawString(4 * inch, height - inch, f"Order ID: {order.id}")
    p.drawString(4 * inch, height - inch - 0.2 * inch, f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
    p.drawString(4 * inch, height - inch - 0.4 * inch, f"Status: {order.status}")
    if order.mpesa_transaction_id:
        p.drawString(4 * inch, height - inch - 0.6 * inch, f"M-Pesa Transaction: {order.mpesa_transaction_id}")

    # Customer details
    p.setFont("Helvetica-Bold", 12)
    p.drawString(inch, height - 1.5 * inch, "Bill To:")
    p.setFont("Helvetica", 10)
    p.drawString(inch, height - 1.7 * inch, f"Name: {order.user.username if order.user else 'Guest'}")
    p.drawString(inch, height - 1.9 * inch, f"Email: {order.user.email if order.user else 'N/A'}")
    p.drawString(inch, height - 2.1 * inch, f"Phone: {order.phone_number if order.phone_number else 'N/A'}")


    # Table Header for items
    y_position = height - 3 * inch
    p.setFont("Helvetica-Bold", 10)
    p.drawString(inch, y_position, "Item")
    p.drawString(3.5 * inch, y_position, "Quantity")
    p.drawString(4.5 * inch, y_position, "Unit Price (KES)")
    p.drawString(6 * inch, y_position, "Total (KES)")
    y_position -= 0.2 * inch
    p.line(inch, y_position, width - inch, y_position) # Draw a line

    # Order Items
    p.setFont("Helvetica", 10)
    total_items_price = 0
    for item in order.orderitem_set.all():
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, item.handbag.name)
        p.drawString(3.5 * inch, y_position, str(item.quantity))
        p.drawString(4.5 * inch, y_position, f"{item.price:,.2f}")
        item_total = item.quantity * item.price
        p.drawString(6 * inch, y_position, f"{item_total:,.2f}")
        total_items_price += item_total
    
    # Summary
    y_position -= 0.4 * inch
    p.line(inch, y_position, width - inch, y_position) # Draw a line
    y_position -= 0.2 * inch

    p.setFont("Helvetica-Bold", 10)
    p.drawString(5 * inch, y_position, "Subtotal:")
    p.drawString(6 * inch, y_position, f"KES {total_items_price:,.2f}")
    y_position -= 0.2 * inch
    p.drawString(5 * inch, y_position, "Shipping:")
    p.drawString(6 * inch, y_position, "KES 0.00") # Assuming free shipping for now
    y_position -= 0.2 * inch
    p.setFont("Helvetica-Bold", 12)
    p.drawString(5 * inch, y_position, "TOTAL:")
    p.drawString(6 * inch, y_position, f"KES {order.total_amount:,.2f}")


    p.showPage()
    p.save()
    return response


# 15. Order Tracking View
@login_required
def order_tracking_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Security check: Ensure the user requesting to track the order owns it
    if order.user != request.user:
        messages.error(request, "You are not authorized to view this order.")
        return redirect('profile') # Redirect to profile page or show a 403 error

    context = {
        'order': order
    }
    return render(request, 'order_tracking.html', context)

# 16. Mpesa access token
def get_access_token(request):
    cl = MpesaClient()
    token = cl.get_access_token()
    return HttpResponse(token)