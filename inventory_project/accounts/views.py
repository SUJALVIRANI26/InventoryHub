from django.shortcuts import render,redirect
from django.http import HttpResponse
from .forms import LoginForm
def login(request):

    if request.method == "POST":
        form = LoginForm(request.POST)
        print(form["email"])
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            role = form.cleaned_data["role"]
            remember = form.cleaned_data.get("remember_me")

            # authentication do here

            if(role == 'admin'):
                return redirect("admin-panel/")
            elif(role == 'inventory_manager'):
                return redirect("inventory_manager/")
            elif(role == 'sales'):
                return redirect("sales/")
            else:
                return redirect("owner/")

    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})
# Create your views here.
