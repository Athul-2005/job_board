from datetime import date
import csv
from django.http import HttpResponse
import logging
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate,logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from datetime import timedelta
from django.utils.timezone import now
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .tasks import send_contact_email_task 
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.conf import settings
from .models import Applicant,Company,Job,Application,Notification

def login_user(request): 
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
 
        if not username or not password:
            messages.error(request, "Both username and password are required.")
            return render(request, "accounts/login.html")
 
        user = authenticate(username=username, password=password)

        if user is not None: 
            try:
                applicant = Applicant.objects.get(user=user)
                if applicant.type == "applicant":
                    login(request, user)
                    return redirect("user:user_homepage")
            except Applicant.DoesNotExist:
                pass   

     
            try:
                company = Company.objects.get(user=user)
                if company.type == "company":
                    login(request, user)
                    return redirect("user:company_homepage")
            except Company.DoesNotExist:
                pass
 
            messages.error(request, "User type not recognized or invalid account.")
        else: 
            messages.error(request, "Invalid username or password.")

        return render(request, "accounts/login.html")
    
    return render(request, "accounts/login.html")



def logout_user(request):
    logout(request)
    return redirect('user:login')



def register_candidates(request):
   if request.method== "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        image = request.FILES.get('image')
        gender = request.POST.get('gender')
        if not username or not email or not first_name or not last_name or not password1 or not password2 or not image or not gender:
            messages.error(request, "All fields are required.")
            return redirect('user:register_candidates')
        
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('user:register_candidates')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('user:register_candidates')
 
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already taken.")
            return redirect('user:register_candidates')
        
        user = User.objects.create_user(
            first_name=first_name, last_name=last_name,
            email=email, username=username, password=password1
        )
        applicant = Applicant.objects.create(
            user=user,email=email,gender=gender,type = 'applicant',
        )
        user.save()
        applicant.save()
        messages.success(request, "Account created successfully. Please log in.")
        return redirect('user:login')  
   return render(request,'accounts/register_candidates.html')

def register_company(request): 
    if request.method == "POST":   
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        phone = request.POST.get('phone') 
        company_name = request.POST.get('company_name')
        image = request.FILES.get('image')   
 
        if not username or not email or not first_name or not last_name or not password1 or not password2 or not phone or not company_name:
            messages.error(request, "All fields are required.")
            return redirect('user:register_company')
 
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('user:register_company')
 
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('user:register_company')
 
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already taken.")
            return redirect('user:register_company')

        #  company profile
        user = User.objects.create_user(
            first_name=first_name, last_name=last_name,
            email=email, username=username, password=password1
        )

        company = Company.objects.create(
            user=user, phone=phone, company_name=company_name,
            image=image, type="company", status="pending"
        )

        user.save()
        company.save()

        messages.success(request, "Account created successfully. Please log in.")
        return redirect('user:login')  

    return render(request, "accounts/register_company.html")


  
def home(request): 
    if request.user.is_authenticated:
        # Applicant
        try:
            applicant = Applicant.objects.get(user=request.user)
            if applicant: 
                query = request.GET.get('q')
                if query:
                    jobs = Job.objects.filter(title__icontains=query).order_by('-creation_date')  # Job search for candidates
                else:
                    jobs = Job.objects.all().order_by('-creation_date')[:5]  # Show all available jobs (limit to 5)
                return render(request, 'home.html', {'jobs': jobs, 'username': request.user.username, 'query': query})
        except Applicant.DoesNotExist:
            pass

        #   Company
        try:
            company = Company.objects.get(user=request.user)
            if company:
                query = request.GET.get('q')
                if query:
                    jobs = Job.objects.filter(title__icontains=query).order_by('-creation_date')  
                else:
                    jobs = Job.objects.all().order_by('-creation_date')[:5]  
                return render(request, 'home.html', {'jobs': jobs, 'username': request.user.username, 'query': query})
        except Company.DoesNotExist:
            pass
         
        return redirect("user:login") 
    else: 
        query = request.GET.get('q')
        if query:
            jobs = Job.objects.filter( 
                     title__icontains=query ,location__icontains=query).order_by('-creation_date')   
        else:
            jobs = Job.objects.all().order_by('-creation_date')[:5]   
            # featured_jobs = Job.objects.filter(featured=True)[:5]  
        return render(request, 'home.html', {'jobs': jobs, 'query': query})







def contact(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        email = request.POST.get('email')
        name = request.POST.get('name')
        
        if not all([subject, message, email]):
            messages.error(request, 'All fields are required')
            return redirect('user:contact')
        
        full_message = f"From: {name}\nEmail: {email}\n\n{message}"
        
        # Call the task with all required arguments
        send_contact_email_task.delay(
            subject=subject,
            message=full_message,
            from_email=email
        )
        
        messages.success(request, 'Your message has been sent!')
        return redirect('user:contact')
    
    return render(request, 'contact.html')

def candidates(request):
    candidates = Applicant.objects.all()
    return render(request,"candidates.html", {'candidates': candidates})

def candidate_details(request, myid):
    candidate = Applicant.objects.get(id=myid)
    return render(request,"candidate_details.html", {'candidate': candidate})
 

def employers(request):
    companies = Company.objects.all() 
    context = {
        'companies': companies,
    }
    return render(request,"employers.html", {'companies': companies})


def company_vacancies(request, company_id):
 
    company = get_object_or_404(Company, id=company_id)
     
    jobs = Job.objects.filter(company=company)
     
    context = {
        'company': company,
        'jobs': jobs,
    }
    
    return render(request, 'company_vacancies.html', context)

def search_results(request):
    query = request.GET.get('q')
    jobs = Job.objects.all()
    companies = Company.objects.all()
    candidates = Applicant.objects.all()

    if query:
        jobs = jobs.filter(title__icontains=query)
        companies = companies.filter(company_name__icontains=query)
        candidates = candidates.filter(user__username__icontains=query)

    return render(request, 'search.html', {
        'jobs': jobs,
        'companies': companies,
        'candidates': candidates,
        'query': query
    })


def job_listing(request):
    query = request.GET.get('q')
    sort_option = request.GET.get('sort', 'creation_date_desc')
    job_types = request.GET.getlist('job_type')
    experiences = request.GET.getlist('experience')
    posted_within = request.GET.getlist('posted_within')

    # Start with all jobs
    jobs = Job.objects.all()

    # Filter by job title (search query)
    if query:
        jobs = jobs.filter(title__icontains=query)

    # Filter by job type
    if job_types:
        jobs = jobs.filter(job_type__in=job_types)

    # Filter by experience
    if experiences:
        jobs = jobs.filter(experience__in=experiences)

    # Filter by posted within (days)
    if posted_within:
        try:
            days_list = [int(days) for days in posted_within]
            days_filter = now() - timedelta(days=min(days_list))
            jobs = jobs.filter(creation_date__gte=days_filter)
        except ValueError:
            pass

    # Define sorting options
    sort_dict = {
        'creation_date_desc': '-creation_date',
        'creation_date_asc': 'creation_date',
        'salary_asc': 'salary',
        'salary_desc': '-salary',
        'title_asc': 'title',
        'title_desc': '-title',
    }

    # Determine the sort field, default is creation_date_desc
    sort_field = sort_dict.get(sort_option, '-creation_date')
    jobs = jobs.order_by(sort_field)

    # Paginator
    paginator = Paginator(jobs, 7)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'job_listing.html', {
        'page_obj': page_obj,
        'query': query,
        'sort_option': sort_option,
        'job_types': job_types,
    })


def job_apply(request, myid): 
    if not request.user.is_authenticated:
        return redirect("login")
    
    applicant = Applicant.objects.get(user=request.user)
    job = get_object_or_404(Job, id=myid)
    date1 = date.today()

    # Check if the job is closed or not open yet
    if job.end_date < date1:
        closed = True
        return render(request, "job_apply.html", {'closed': closed})
    elif job.start_date > date1:
        notopen = True
        return render(request, "job_apply.html", {'notopen': notopen})
    
    # Check if the applicant has already applied for this job
    existing_application = Application.objects.filter(job=job, applicant=applicant).exists()
    if existing_application: 
        messages.error(request, "You have already applied for this job.")
        return render(request, "job_apply.html", {'job': job})

    # Handle POST request for job application
    if request.method == "POST": 
        # Check if resume is provided in the request
        if 'resume' not in request.FILES:
            messages.error(request, "All fields are required. Please upload your resume.")
            return render(request, "job_apply.html", {'job': job})

        # Get the resume from the uploaded files
        resume = request.FILES['resume']

        # Create a new application
        Application.objects.create(
            job=job,
            company=job.company,
            applicant=applicant,
            resume=resume,
            apply_date=date.today()
        )

        # Show success message and return response
        messages.success(request, "You have successfully applied for the job!")
        return render(request, "job_apply.html", {'alert': True, 'job': job})

    return render(request, "job_apply.html", {'job': job})


def applied_jobs(request):
    if request.user.is_authenticated:
        try: 
            applicant = Applicant.objects.get(user=request.user)
             
            applied_jobs = Application.objects.filter(applicant=applicant).select_related('job').order_by('-apply_date')
           
            applied_jobs_count = applied_jobs.count()
             
            return render(request, 'admin/candidates/applied_jobs.html',   {
                           
                           'applied_jobs': applied_jobs, 
                           'applied_jobs_count': applied_jobs_count, 
                           'username': request.user.username
                           
                           })
        
        except Applicant.DoesNotExist:
            return redirect('login')
    else:
        return redirect('login')


def delete_applied_job(request, application_id):
    if request.user.is_authenticated:
        applicant = get_object_or_404(Applicant, user=request.user)        
        application = get_object_or_404(Application, id=application_id, applicant=applicant)   
        application.delete()     
        messages.success(request, "Application deleted successfully.")   
        return redirect('applied_jobs')
    else:
        return redirect('login')
# def all_applicants(request):
#     company = Company.objects.get(user=request.user)
#     application = Application.objects.filter(company=company)
#     return render(request, "admin/employers/all_applicants.html", {'application':application})    

def all_applicants(request):
    company = Company.objects.get(user=request.user)

    if request.method == 'POST':
        application_id = request.POST.get('application_id')
        new_status = request.POST.get('status')
        application = get_object_or_404(Application, id=application_id, company=company)

        # Check if the application status has already been set
        # if application.status:
        #     messages.error(request, "The status for this application has already been updated and cannot be changed again.")
        #     return redirect('all_applicants')  # Redirect without making changes
 
        application.status = new_status
        application.save()

        # Send notification to the applicant
        applicant_user = application.applicant.user  
        if new_status == 'accepted':
            notification_message = f"Your application for   {application.job}  has been accepted."
            messages.success(request, notification_message)
        elif new_status == 'rejected':
            notification_message = f"Your application for   {application.job}  has been rejected."
            messages.warning(request, notification_message)
 
        Notification.objects.create(
            user=applicant_user,
            message=notification_message
        )

        return redirect('all_applicants')
 
    application_list = Application.objects.filter(company=company)

    return render(request, "admin/employers/all_applicants.html", {
        'application': application_list,
    })



def delete_applicant(request, id):
    application = get_object_or_404(Application, id=id)
    
    if request.method == 'POST':
        application.delete()
        messages.success(request, "Application deleted successfully.")
        return redirect('all_applicants')  

    return redirect('all_applicants')  

 

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('user:login')  # Or home page if you prefer
    else:
        # Show confirmation page or redirect
        return render(request, 'accounts/confirm_delete.html')
 #company 

def company_homepage(request):
       # Assuming each user has one company, get the company related to the logged-in user
    if request.user.is_authenticated:
        # Get the company for the authenticated user
        company = Company.objects.get(user=request.user)
        
        context = {
            'company': company,  # Pass the company to the template
        }
        return render(request, 'admin/employers/company_homepage.html', context)
    else:
        return redirect('login')  # Redirect to login if not authenticated


def company_profile(request):
    if not request.user.is_authenticated:
        return redirect("login")
    company = Company.objects.get(user=request.user)
    if request.method=="POST":   
        company_name = request.POST['company_name']
        first_name=request.POST['first_name']
        last_name=request.POST['last_name']
        phone = request.POST['phone'] 
        description = request.POST['description']
        website = request.POST['website']
        
 
        company.company_name = company_name
        company.user.first_name = first_name
        company.user.last_name = last_name
        company.phone = phone  
        company.description = description
        company.website = website
        company.save()
        company.user.save()
 
        try:
            image = request.FILES['image']
            company.image = image
            company.save()
        except:
            pass
        alert = True
        # return render(request, "admin/employers/company_profile.html", {'alert':alert})
        return redirect('user:company_profile') 
    return render(request, "admin/employers/company_profile.html", {'company':company})




def add_job(request):
    if not request.user.is_authenticated:
        return redirect("login")       
    if request.method == "POST":
        title = request.POST['job_title']
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        salary = request.POST['salary']
        image = request.FILES['logo']
        experience = request.POST['experience']
        location = request.POST['location']
        skills = request.POST['skills']
        description = request.POST['description'] 
        
        job_type = request.POST['job-Type']  
        work_location = request.POST['Work-location']   

        user = request.user
        company = Company.objects.get(user=user)
        job = Job.objects.create(company=company, title=title,start_date=start_date, end_date=end_date, salary=salary, 
                                 image=image, experience=experience, location=location, skills=skills, description=description,job_type=job_type,
                                 work_location=work_location, creation_date=date.today())
        job.save()
        messages.success(request, 'Job added successfully!') 
   
        alert = True
        return render(request, "admin/employers/add_job.html", {'alert':alert}) 
     
    return render(request, "admin/employers/add_job.html")



@login_required
def edit_job(request, myid):
    job = get_object_or_404(Job, id=myid)

    if request.user != job.company.user:
        messages.error(request, "You are not authorized to edit this job.")
        return redirect('job_list')

    if request.method == "POST":
        job.title = request.POST.get('job_title')
        job.start_date = request.POST.get('start_date') or job.start_date
        job.end_date = request.POST.get('end_date') or job.end_date
        job.salary = request.POST.get('salary')
        job.experience = request.POST.get('experience')
        job.location = request.POST.get('location')
        job.skills = request.POST.get('skills')
        job.description = request.POST.get('description')
        job.job_type = request.POST.get('job-Type')
        job.work_location = request.POST.get('Work-location')

        if 'logo' in request.FILES:
            job.image = request.FILES['logo']

        job.save()
        messages.success(request, "Job updated successfully.")
        return redirect('user:job_detail', myid=job.id)

    return render(request, "admin/employers/edit_job.html", {'job': job})



def job_details(request, myid):
    job = Job.objects.get(id=myid)
    return render(request,"job_details.html", {'job':job})

  
def job_list(request):
    if not request.user.is_authenticated:
        return redirect("login")
    companies = Company.objects.get(user=request.user)
    jobs = Job.objects.filter(company=companies)
    return render(request, "admin/employers/job_list.html", {'jobs':jobs})

def job_detail(request, myid):
    job = Job.objects.get(id=myid)
    return render(request, "admin/employers/job_detail.html", {'job':job})

def delete_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    if request.method == 'POST':
        job.delete()
        messages.success(request, "Job deleted successfully.")
        return redirect('job_list')  

    return redirect('job_list')

def settings(request):
    if not request.user.is_authenticated:
        return redirect('/login/') 

    password_form = PasswordChangeForm(user=request.user)

    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # Keep user logged in after password change
            messages.success(request, 'Your password was successfully changed!')
            return redirect('settings')  # Redirect to the same settings page after a successful password change
        else:
            messages.error(request, 'Please correct the error(s) below.')

    return render(request, "admin/settings.html", {
        'password_form': password_form
    })

 


#  User Candidate

def user_homepage(request):
    if not request.user.is_authenticated:
        return redirect('login/')

    # Fetch unread notifications for the logged-in user
    notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')

    return render(request, "admin/candidates/user_homepage.html", {
        'notifications': notifications,
    })


def notification(request):
    if not request.user.is_authenticated:
        return redirect('login/')
    
    notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
    
    return render(request,"admin/candidates/notification.html" , {
        'notifications': notifications,
    })

 
def user_profile(request):
    if not request.user.is_authenticated:
        return redirect('/login/') 
    
    applicant = Applicant.objects.get(user=request.user)

    if request.method=="POST":   
        email = request.POST['email']
        first_name=request.POST['first_name']
        last_name=request.POST['last_name']
        phone = request.POST['phone']
        gender = request.POST['gender']
        work = request.POST['work']
        year = request.POST['year']
        education_level = request.POST['education_level']
        location = request.POST['location']
        district=request.POST['district']
        state=request.POST['state']
        country=request.POST['country']
        pincode=request.POST['pincode']
        about = request.POST['about']
        
 
        applicant.user.email = email
        applicant.user.first_name = first_name
        applicant.user.last_name = last_name
        applicant.phone = phone
        applicant.gender = gender
        applicant.work = work
        applicant.year = year
        applicant.location = location
        applicant.district=district
        applicant.country=country
        applicant.state=state
        applicant.pincode=pincode
        applicant.education_level = education_level
        applicant.about = about
        applicant.save()
        applicant.user.save()
 
        # Safely handle image and CV upload using .get() to avoid MultiValueDictKeyError
        if 'image' in request.FILES:
            applicant.image = request.FILES['image']
        
        if 'cv' in request.FILES:  # Check if 'cv' is in request.FILES before accessing it
            applicant.cv = request.FILES['cv']
        
        applicant.save()

        
        messages.success(request, 'Your form was successfully submitted!') 
        return redirect('user:user_profile')  

    
    return render(request, "admin/candidates/user_profile.html", {'applicant':applicant})


def all_download(request):
    application_list = Application.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="applications.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Company', 'Job','Start Date','Deadline','Required Skills','Required Experience', 'Job Type','Work Mode',
        'Applicant','Email', 'PassedOut Year', 'Gender', 'Phone','Education', 'Resume', 'Experience', 
        'Candidate Place','Candidate District','Candidate State','Candidate Country','Candidate Pincode',
        'Type','Applied On', 'Status'
    ])

    for app in application_list:
        applicant = app.applicant
        job=app.job
        writer.writerow([
            str(app.company),  # FK
            str(app.job),     # FK
            job.start_date,
            job.end_date,
            job.skills,
            job.experience,
            job.job_type,
            job.work_location,
            applicant.user.get_full_name(),  # Applicant full name from User model
            app.applicant.user.email,   # ✅ From Applicant model
            applicant.year,
            applicant.gender,
            applicant.phone,
            applicant.education_level,
            str(app.resume),  # File URL if resume exists
            applicant.work,
            applicant.location,
            applicant.district,
            applicant.state,
            applicant.country,
            applicant.pincode,
            applicant.type,
            app.apply_date.strftime('%Y-%m-%d') if app.apply_date else '',
            app.status
        ])

    return response

def about(request):

    return render(request,'about.html')

def forgot_password(request):
    return render(request,'accounts/forgot.html')