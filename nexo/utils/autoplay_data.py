"""
Autoplay data: artists, aliases, topics (mood / playlist / devotional / festival ...).

Isko `nexo/utils/autoplay_data.py` naam se rakho.

NOTE: YouTube par har artist ka naam is list mein nahi aa sakta. Isliye 3 layer hain:
  1. Ye built-in list (niche, sab languages)
  2. Jo artist is list mein nahi, bot usse YouTube search se pehchanta hai
     aur `autoplay_artists` collection mein seekh leta hai (agli baar seedha pehchan lega)
  3. Nayi list khud jodni ho to `ARTISTS` mein naam daal do ya
     autoplay_context_db.add_artist("naam", ["alias", ...]) call karo.

Naam comma se alag, kisi bhi spelling mein (lowercase ya capital, farq nahi padta).
"""

ARTISTS = {
    # ------------------------------------------------------------ BHOJPURI
    "bhojpuri": """
        Pawan Singh, Khesari Lal Yadav, Arvind Akela Kallu, Dinesh Lal Yadav Nirahua,
        Ritesh Pandey, Samar Singh, Tuntun Yadav, Shilpi Raj, Neelkamal Singh,
        Pramod Premi Yadav, Gunjan Singh, Antra Singh Priyanka, Kalpana Patowary,
        Indu Sonali, Priyanka Singh, Khushboo Uttam, Khushboo Jain, Alka Jha,
        Shivani Singh, Ankush Raja, Pradeep Pandey Chintu, Amrita Dixit, Rakesh Mishra,
        Bharat Sharma Vyas, Mohan Rathore, Awadhesh Premi Yadav, Manoj Tiwari,
        Ravi Kishan, Ashish Yadav, Dhananjay Mishra, Monu Albela, Lado Madheshiya,
        Golu Gold, Chandan Chanchal, Bablu Ajnabi, Alok Kumar, Deepak Dildar,
        Raushan Rohi, Sunil Chhaila Bihari, Kajal Raghwani, Akshara Singh,
        Amrapali Dubey, Anjana Singh, Monalisa, Priyanka Pandit, Shweta Mahara,
        Kavita Yadav, Neha Raj, Nisha Upadhyay, Pushpa Rana, Ritu Singh,
         Ajeet Anand, Ankit Anand, Anu Dubey, Mamta Raut,
        Rinku Ojha, Sonu Sargam, Mukesh Premi, Vijay Lal Yadav, Prem Prakash Dubey,
        Rani Chatterjee, Dinesh Lal Yadav, Sandeep Yadav, Ravi Chauhan, Rahul Gupta,
    """,
    # ------------------------------------------------------------ HARYANVI / RAJASTHANI
    "haryanvi_rajasthani": """
        Sapna Choudhary, Renuka Panwar, Masoom Sharma, Ajay Hooda, Raju Punjabi,
        Diler Kharkiya, Vijay Varma, Pranjal Dahiya, KD, Ruchika Jangid,
        Amit Saini Rohtakiya, Gulzaar Chhaniwala, Sumit Goswami, Anjali Raghav,
        Bintu Pabra, Mukesh Jaji, Narender Bhagana, Somvir Kathurwal, Ashu Twinkle,
        Sonika Singh,  Pardeep Boora, Vishvajeet Choudhary,
        Seema Mishra, Maithili Thakur, Mame Khan, Swaroop Khan, Gazi Khan Barna,
        Anwar Khan Manganiyar, Rekha Rao, Prakash Mali, Teju Mali, Lakhi Singh,
        Kutle Khan, Mohan Singh Rathore, Narendra Singh Negi, Gajendra Rana,
        Pritam Bharatwan, Meena Rana, 
    """,
    # ------------------------------------------------------------ HINDI male / composers
    "hindi_male": """
        Arijit Singh, Atif Aslam, Sonu Nigam, Kumar Sanu, Udit Narayan, Mohit Chauhan,
        KK, Shaan, Sukhwinder Singh, Mika Singh, Badshah, Yo Yo Honey Singh, Raftaar,
        Divine, Emiway Bantai, King, MC Stan, Jubin Nautiyal, Darshan Raval,
        Armaan Malik, Amaal Mallik, Vishal Mishra, B Praak, Ankit Tiwari,
        Mohammad Irfan, Papon, Rahat Fateh Ali Khan, Nusrat Fateh Ali Khan,
        Abhijeet Bhattacharya, Kishore Kumar, Mohammed Rafi, Mukesh, Manna Dey,
        Hemant Kumar, Talat Mahmood, Jagjit Singh, Ghulam Ali, Pankaj Udhas,
        Anup Jalota, Hariharan, Shankar Mahadevan, Lucky Ali, Himesh Reshammiya,
        Vishal Dadlani, Benny Dayal, Neeraj Shridhar, Sachin Jigar, Pritam,
        A R Rahman, Amit Trivedi, Shankar Ehsaan Loy, Vishal Shekhar, Salim Sulaiman,
        Tanishk Bagchi, Mithoon, Sajid Wajid, Anu Malik, Nadeem Shravan, Jatin Lalit,
        Anand Milind, Laxmikant Pyarelal, R D Burman, S D Burman, O P Nayyar,
        Ravindra Jain, Yasser Desai, Stebin Ben, Rochak Kohli, Gajendra Verma,
        Ash King, Farhan Saeed, Falak Shabir, Sachet Tandon, Javed Ali, Zubeen Garg,
        Sanam Puri, Raghav Chaitanya, Ritviz, Prateek Kuhad, Anuv Jain, Vayu,
        Kaifi Khalil, Dev Negi, Ikka, Seedhe Maut, Kr$na, Krsna, Hanumankind,
        Talwiinder,  Sunny Malton, Hardy Sandhu, Mohammed Aziz,
        Shabbir Kumar, Suresh Wadkar, Roop Kumar Rathod, Sudesh Bhosle,
        Amit Kumar, Jolly Mukherjee, Bappi Lahiri, Kailash Kher, Rabbi Shergill,
         Mahendra Kapoor, Bhupinder Singh, Chitra Singh,
        Ankur Tewari, Siddharth Mahadevan, Rahul Vaidya, Aditya Narayan,
        Rajeev Raja, Gaurav Chatterji, Sumeet Tappoo, Palash Muchhal,
        Mohd Danish, Pawandeep Rajan, Salman Ali, Shahid Mallya, Vipul Mehta,
    """,
    # ------------------------------------------------------------ HINDI female
    "hindi_female": """
        Shreya Ghoshal, Lata Mangeshkar, Asha Bhosle, Alka Yagnik, Sunidhi Chauhan,
        Neha Kakkar, Tulsi Kumar, Shilpa Rao, Palak Muchhal, Monali Thakur,
        Kanika Kapoor, Dhvani Bhanushali, Jonita Gandhi, Neeti Mohan,
        Shalmali Kholgade, Harshdeep Kaur, Rekha Bhardwaj, Richa Sharma,
        Anuradha Paudwal, Kavita Krishnamurthy, Sadhana Sargam, Sapna Awasthi,
        Asees Kaur, Akasa Singh, Prakriti Kakar, Aakriti Kakar, Sukriti Kakar,
        Payal Dev, Neha Bhasin, Jyotica Tangri, Antara Mitra, Madhubanti Bagchi,
        Mamta Sharma, Kaur B, Vaishali Mhade, Nikita Gandhi, Ila Arun, Usha Uthup,
        Geeta Dutt, Suraiya, Noor Jehan, Runa Laila, Abida Parveen, Iqbal Bano,
        Farida Khanum, Jasleen Royal, Parampara Thakur, Aastha Gill, Shirley Setia,
        Zara Khan, Sanjeeda Shaikh, Sona Mohapatra, Mahalakshmi Iyer, Shweta Pandit,
        Sunita Rao, Anusha Mani, Sharvi Yadav,  Ananya Birla,
        Rashmeet Kaur, Kavita Seth,  Mohini Dey, 
        Bhumi Trivedi, Ritu Pathak, Swaroop Bhalwankar, Deepali Sathe, 
    """,
    # ------------------------------------------------------------ PUNJABI
    "punjabi": """
        Sidhu Moose Wala, Diljit Dosanjh, AP Dhillon, Karan Aujla, Guru Randhawa,
        Jassie Gill, Ammy Virk, Jass Manak, Sharry Maan, Gippy Grewal, Harrdy Sandhu,
        Mankirt Aulakh, Amrinder Gill, Babbu Maan, Gurdas Maan, Hans Raj Hans,
        Sukhe, Jazzy B, Daler Mehndi, Malkit Singh, Kuldeep Manak, Surinder Shinda,
        Satinder Sartaaj, Kulwinder Billa, Nimrat Khaira, Sunanda Sharma,
        Gurnam Bhullar, Ninja, Sajjan Adeeb, Parmish Verma, Shubh, Jordan Sandhu,
        R Nait, Afsana Khan, Miss Pooja, Gur Sidhu, Navaan Sandhu, Kaka, Bohemia,
        Imran Khan Punjabi, Jasmine Sandlas, Ranjit Bawa, Bilal Saeed, Garry Sandhu,
        Roshan Prince, Veet Baljit, Mannat Noor, Gulab Sidhu, Himmat Sandhu,
        Inderjit Nikku, Deep Jandu, Elly Mangat, Arjan Dhillon, Amar Sandhu,
        Sukh E,  Lehmber Hussainpuri, Sarbjit Cheema, Manmohan Waris,
        Kamal Heer, Sangtar, Hardeep Grewal, Dilpreet Dhillon, Inder Chahal,
        Ravneet Singh, Nirvair Pannu,  Tarsem Jassar,
        Harbhajan Mann, Sardool Sikander, Amar Singh Chamkila, Surjit Bindrakhia,
        Gurlez Akhtar, Resham Singh Anmol, Amrit Maan,  Yo Yo Honey Singh,
        Gurinder Seagal, Preet Harpal, Jaggi Singh, Prabh Gill, Nachhatar Gill,
        Prabh Singh, Baaghi, Mahi Sharma, Hustinder, Feroz Khan Punjabi, Diljaan,
        Kulwinder Dhillon, Jasmeen Akhtar, Gagan Kokri, Nawab, Sultaan, Jaz Dhami,
    """,
    # ------------------------------------------------------------ GUJARATI / MARATHI
    "gujarati_marathi": """
        Kinjal Dave, Geeta Rabari, Kirtidan Gadhvi, Jignesh Kaviraj, Aishwarya Majmudar,
        Rakesh Barot, Vijay Suvada, Arvind Barot, Bhikhudan Gadhvi, Alpa Patel,
        Gaman Santhal, Mamta Soni, Hemant Chauhan, Praful Dave, Osman Mir,
        Parthiv Gohil, Falguni Pathak, Atul Purohit, Jigardan Gadhavi, Divya Kumar,
        Sachin Limbachiya, Kajal Maheriya, Farida Meer, Dhaval Barot, Mayur Soni,
        Ajay Atul, Adarsh Shinde, Anand Shinde, Milind Shinde, Avadhoot Gupte,
        Vaishali Samant, Bela Shende, Swapnil Bandodkar, Hrishikesh Ranade,
        Aarya Ambekar, Mugdha Vaishampayan, Sachin Pilgaonkar, Nandesh Umap,
        Jasraj Joshi, Ketaki Mategaonkar, Sayali Kamble, Rohit Raut, Shreya Bugde,
        Guru Thakur, Pravin Kuwar, Vitthal Umap, Sanjivani Bhelande, Savani Ravindra,
        Anuradha Paudwal Marathi, Arun Date, Asha Khadilkar, Prahlad Shinde,
    """,
    # ------------------------------------------------------------ BENGALI / ASSAMESE / ODIA
    "bengali_assamese_odia": """
        Anupam Roy, Rupam Islam, Anjan Dutt, Hemanta Mukherjee, Sandhya Mukhopadhyay,
        Lopamudra Mitra, Ujjaini Mukherjee, Iman Chakraborty, Nachiketa, Kabir Suman,
        Srikanto Acharya, Indrani Sen, Debabrata Biswas, Suchitra Mitra,
        Kanika Banerjee, Paban Das Baul, Lalon Fakir, Anupam Roy Songs,
        Jeet Gannguli, Arindom, Raghab Chatterjee, Timir Biswas, Shaan Bengali,
        Jojo, Somlata Acharyya Chowdhury, Ananya Chakraborty, Arijit Singh Bengali,
        Angarag Mahanta Papon, Zubeen Garg Assamese, Jonaki Borah, Nilotpal Bora,
        Bhupen Hazarika, Dikshu, Rupjyoti, Humane Sagar, Sanjit Mohanty,
        Abhijit Majumdar, Tapu Mishra, Ira Mohanty, Anuradha Paudwal Odia,
        Satyajit Pradhan, Asima Panda, Diptirekha Padhi, Kumar Bapi,
    """,
    # ------------------------------------------------------------ TAMIL
    "tamil": """
        Ilaiyaraaja, Anirudh Ravichander, Yuvan Shankar Raja, Harris Jayaraj,
        D Imman, G V Prakash Kumar, Santhosh Narayanan, Sid Sriram,
        S P Balasubrahmanyam, K S Chithra, Unnikrishnan, Karthik, Haricharan,
        Vijay Yesudas, K J Yesudas, S Janaki, P Susheela, Swarnalatha, Chinmayi,
        Andrea Jeremiah, Dhee, Sean Roldan, Dhanush, Silambarasan, Vijay Prakash,
        Naresh Iyer, Mano, Malgudi Subha, Srinivas, Gana Bala, Anthony Daasan,
        Pradeep Kumar, Shashaa Tirupati, Sathyaprakash, Hiphop Tamizha, Ghibran,
        Leon James, Sam C S, Shweta Mohan, Mahathi, Vandana Srinivasan, Aalaap Raju,
        Deva, Vidyasagar Tamil, Bharadwaj, Srikanth Deva, Vijay Antony,
        Hip Hop Tamizha Adhi, Rahul Nambiar, Bombay Jayashree, Harini, Sadhana Sargam Tamil,
        T M Soundararajan, M S Viswanathan, Kannadasan, Ramesh Vinayakam,
        Rajhesh Vaidhya, Gopi Sundar Tamil, Shankar Mahadevan Tamil, 
        Dhibu Ninan Thomas, Santhosh Dhayanidhi, Jakes Bejoy, Justin Prabhakaran,
        Kaushik Krish, Sundar C Babu, Thaman Tamil, Pradeep Ranganathan,
    """,
    # ------------------------------------------------------------ TELUGU
    "telugu": """
        Devi Sri Prasad, S S Thaman, M M Keeravani, Anup Rubens, Mickey J Meyer,
        Gopi Sunder, Anurag Kulkarni, Rahul Sipligunj, Kaala Bhairava, Hema Chandra,
        Geetha Madhuri, Mangli, Revanth, Ramya Behara, Sunitha, Dhanunjay,
        Ghantasala, Sri Krishna, Ram Miriyala, Ranina Reddy, Lipsika, Yazin Nizar,
        Shankar Babu Kandukuri, Jassie Gift, Karthik Telugu, Mani Sharma,
        Koti, Chakri, R P Patnaik, Ravi Varma, Sahithi Chaganti, Anantha Sriram,
        Chandrabose, Sirivennela, Vijay Bulganin, Harris Jayaraj Telugu,
        Hari Priya, Sahiti, Satya Yamini, Sai Charan, Mohana Bhogaraju,
        Madhu Priya, Bhaskarabhatla, Rahman Telugu, Prudhvi Chandra,
        Deepu, Saketh Komanduri, Sagar, Ritesh G Rao, Nutana Mohan,
    """,
    # ------------------------------------------------------------ MALAYALAM / KANNADA
    "malayalam_kannada": """
        M G Sreekumar, Vineeth Sreenivasan, Shaan Rahman, Sushin Shyam,
        Hesham Abdul Wahab, Sithara Krishnakumar, Najim Arshad, Jyotsna,
        Sujatha Mohan, G Venugopal, Pradeep Palluruthy, Job Kurian, Ranjith Govind,
        Afsal, Madhu Balakrishnan, P Jayachandran, Rahul Raj, Bijibal,
        Prashant Pillai, Ouseppachan, M Jayachandran, Alphons Joseph, Anne Amie,
        Gopi Sundar, Vidyasagar, Ravi Basrur, Rajesh Krishnan, Sanjith Hegde,
        Arjun Janya, V Harikrishna, Charan Raj, Anup Bhandari, Dr Rajkumar,
        Chandan Shetty, Puneeth Rajkumar, Vasuki Vaibhav, Supriya Lohith,
        Anuradha Bhat, Ananya Bhat, Shamitha Malnad, Vijay Prakash Kannada,
        Sonu Nigam Kannada, Karthik Kannada, Nakul Abhyankar, Ajaneesh Loknath,
        Hamsalekha, Rajan Nagendra, Kailash Kher Kannada, Shreya Ghoshal Kannada,
        Armaan Malik Kannada, Nanditha, Indu Nagaraj, Mangli Kannada,
    """,
    # ------------------------------------------------------------ DEVOTIONAL
    "devotional": """
        Hari Om Sharan, Gulshan Kumar, Narendra Chanchal, Lakhbir Singh Lakha,
        Sanjo Baghel, Kanhaiya Mittal, Hansraj Raghuwanshi, Hemant Brijwasi,
        Vinod Agarwal, Pandit Jasraj, Pandit Bhimsen Joshi, M S Subbulakshmi,
        Jaya Kishori, Devi Chitralekha, Anuradha Paudwal Bhajan, Sanjay Mittal,
        Vikram Singh Rana, Rakesh Kala, Sonu Nigam Bhakti, Pt Ravi Shankar,
        Pandit Birju Maharaj, Sadhvi Purnima, Neha Kakkar Bhakti, Ravindra Jain Bhajan,
        Pradeep Pandey Bhakti, Sukhwinder Singh Bhakti, Gurdas Maan Bhakti,
        Bhajan Samrat Anup Jalota, Anup Jalota Bhajan, Ravi Raj, Tripti Shakya,
        Mamta Sharma Bhakti, Deepali Sathe Bhakti, Rajan Sajan Mishra, Pt Jasraj,
        Narayan Sharma, Pujya Jaya Kishori Ji, Pujya Rajan Ji, Krishna Das,
        Bhai Harjinder Singh, Bhai Ravinder Singh, Bhai Davinder Singh Sodhi,
        Bhai Gurmeet Singh, Bhai Joginder Singh Riar, Bhai Maninder Singh,
        Bhai Harbans Singh Jagadhri, Bhai Amarjit Singh Patiala,
    """,
    # ------------------------------------------------------------ PAKISTANI / URDU / GHAZAL / SUFI
    "pakistani_urdu": """
        Ali Zafar, Asim Azhar, Hadiqa Kiani, Strings, Junoon, Quratulain Balouch,
        Shafqat Amanat Ali, Ali Sethi, Momina Mustehsan, Sajjad Ali, Zeb And Haniya,
        Coke Studio, Overload,  Rahat Fateh Ali Khan Qawwali,
        Sabri Brothers, Amjad Sabri, Aziz Mian, Ustad Mehdi Hassan, Mehdi Hassan,
        Ghulam Ali Ghazal, Tahira Syed, Nayyara Noor, Alamgir, Nazia Hassan, Zoheb Hassan,
        Fakhar E Alam, Ali Azmat, Abrar Ul Haq, Ahmed Jahanzeb, Sahir Ali Bagga,
        Naseebo Lal, Shiraz Uppal, Faakhir Mehmood, Rizwan Butt, Shani Arshad,
        Atif Aslam Pakistan, Farhan Saeed Pakistan, Jal The Band, Ali Noor,
        Hamza Malik, Umair Jaswal, Bilal Khan, Sahir Ali, Abdullah Qureshi,
        Wajid Ali Baghdadi, Jawad Ahmed, Fariha Pervez, Malika Pukhraj, Reshma,
    """,
    # ------------------------------------------------------------ ENGLISH / INTERNATIONAL
    "english": """
        Taylor Swift, Ed Sheeran, Justin Bieber, The Weeknd, Drake, Billie Eilish,
        Ariana Grande, Dua Lipa, Adele, Bruno Mars, Coldplay, Imagine Dragons,
        Maroon 5, Selena Gomez, Shawn Mendes, Charlie Puth, Sam Smith, Harry Styles,
        Olivia Rodrigo, Post Malone, Eminem, Rihanna, Beyonce, Lady Gaga, Katy Perry,
        Shakira, Camila Cabello, Sia, Halsey, Lana Del Rey, Doja Cat, SZA,
        Bad Bunny, J Balvin, Maluma, Ozuna, Karol G, Daddy Yankee, Luis Fonsi,
        Enrique Iglesias, Jennifer Lopez, Pitbull, Michael Jackson, Elvis Presley,
        The Beatles, Queen, Linkin Park, Metallica, Nirvana, Guns N Roses, AC DC,
        Pink Floyd, Led Zeppelin, Eagles, Bon Jovi, Green Day, Red Hot Chili Peppers,
        Twenty One Pilots, OneRepublic, Avicii, Alan Walker, Marshmello,
        Martin Garrix, David Guetta, Calvin Harris, Zedd, The Chainsmokers, Kygo,
        Tiesto, Skrillex, Diplo, Swedish House Mafia, Eric Clapton, Bob Marley,
        Bob Dylan, Frank Sinatra, Whitney Houston, Celine Dion, Mariah Carey,
        Backstreet Boys, Westlife, Boyzone, NSYNC, One Direction, Ellie Goulding,
        Rag N Bone Man, James Arthur, Lewis Capaldi, Tom Odell, Passenger,
        Jason Mraz, John Legend, Alicia Keys, Usher, Chris Brown, Nicki Minaj,
        Cardi B, Travis Scott, Kendrick Lamar, Jay Z, Kanye West, 50 Cent,
        Snoop Dogg, Dr Dre, 2Pac, Notorious B I G, Lil Wayne, Future, Juice WRLD,
        XXXTentacion, Lil Nas X, Megan Thee Stallion, Khalid, Dean Lewis, Ruth B,
        Alessia Cara, Zayn Malik, Niall Horan, Louis Tomlinson, Liam Payne,
        Jonas Brothers, Demi Lovato, Miley Cyrus, Britney Spears, Christina Aguilera,
        Kelly Clarkson, Avril Lavigne, Sabrina Carpenter, Chappell Roan, Tate McRae,
        Teddy Swims, Noah Kahan, Benson Boone, Hozier, Lizzo, Gracie Abrams,
        Conan Gray, Maneskin, Rema, Burna Boy, Wizkid, Tems, Ayra Starr, Davido,
        Akon, Sean Paul, Shaggy, Nelly Furtado, Lauv, Jeremy Zucker, Anne Marie,
        Meghan Trainor, Jessie J, Rita Ora, Little Mix, Fifth Harmony, Spice Girls,
        ABBA, Bee Gees, Dire Straits, Scorpions, Sting, Phil Collins, Ricky Martin,
        Ne Yo, Akon, Flo Rida, Lil Jon, Ludacris, Tyga, Machine Gun Kelly,
        Arctic Monkeys, The Killers, Radiohead, Oasis, Muse, Keane, The Script,
        Gotye, Sam Fender, Dermot Kennedy, Alec Benjamin, Mac Miller, Logic,
        Tones And I, Glass Animals, Joji, Steve Lacy, Frank Ocean, The Neighbourhood,
        Arijit Singh English,  Ava Max, Bebe Rexha, Normani, Cher,
        Madonna, Prince, David Bowie, Rolling Stones, The Doors, Santana, Enya,
    """,
    # ------------------------------------------------------------ K-POP / J-POP / WORLD
    "kpop_world": """
        BTS, Blackpink, Jungkook, Jimin, Suga, RM, J Hope, Lisa, Jennie, Jisoo,
        Rose, Stray Kids, Twice, NewJeans, Seventeen, EXO, Red Velvet, ITZY, aespa,
        IVE, Le Sserafim, TXT, Enhypen, Ateez, Psy, IU, GOT7, Monsta X, NCT,
        Big Bang, G Dragon, Taeyeon, Girls Generation, Kim Taehyung, V BTS,
        Yoasobi, Kenshi Yonezu, Ado, Official Hige Dandism, Lisa Japanese,
        Amr Diab, Nancy Ajram, Fairuz, Umm Kulthum, Kadim Al Sahir, Mohammed Assaf,
        Tamer Hosny, Elissa, Hussain Al Jassmi, Cheb Khaled, Rim Banna, Saad Lamjarred,
        Ricardo Arjona, Juanes, Shakira Spanish, Rosalia, Anitta, Rauw Alejandro,
        Feid, Peso Pluma, Natanael Cano, Grupo Frontera, Romeo Santos, Prince Royce,
        Aya Nakamura, Stromae, Zaz, Edith Piaf, Charles Aznavour, Joe Dassin,
        Tarkan, Sezen Aksu, Kenan Dogulu, Mabel Matiz, Zeynep Bastik,
        Dima Bilan, Sergey Lazarev, Polina Gagarina, Ani Lorak, Jony,
        Jay Chou, Jolin Tsai, Teresa Teng, Eason Chan, JJ Lin, Faye Wong,
    """,
    # ------------------------------------------------------------ CHANNELS / LABELS (YouTube)
    "channels": """
        T Series, Zee Music Company, Sony Music India, Saregama Music, Tips Official,
        Speed Records, Wave Music, Goldmines, Shemaroo, Venus, Worldwide Records Bhojpuri,
        Jhankar Music, Lahari Music, Aditya Music, Think Music India, Sun Music,
        Times Music, Eros Now Music, YRF, Yash Raj Films, Universal Music India,
        Gaana Originals, Mixtape Rewind, Coke Studio Bharat, Coke Studio Pakistan,
        MTV Unplugged, Cokestudio, Sa Re Ga Ma Pa, Indian Idol, Star Plus,
        Hungama Music, Muzik247, Yellow Music, Vevo, Spinnin Records, NCS, Trap Nation,
         Anand Audio, Bhakti Sagar, Shemaroo Bhakti, Ambey Bhakti,
        Bhojpuri Dhamaka, Bhojpuri Music Station, Hamaar Bhojpuri, Maahi Music,
        Rajasthani Songs, Anjani Music, Vishnu Music, Star Audio, Sagar Music Studio,
        Jhankar Beats, Lofi Girl, Chillhop Music, Ultra Music, Monstercat, Mad Decent,
    """,
}

# Alag spelling / short naam  ->  asli (canonical) naam.
# Canonical naam ARTISTS list mein jaisa hai waisa hi likho.
ALIASES = {
    "Pawan Singh": ["pavan singh", "pawan sing", "पवन सिंह"],
    "Khesari Lal Yadav": ["khesari lal", "khesari", "khesarilal", "खेसारी लाल यादव", "खेसारी लाल"],
    "Arvind Akela Kallu": ["arvind akela", "arvind kallu", "kallu ji", "अरविंद अकेला कल्लू"],
    "Dinesh Lal Yadav Nirahua": ["nirahua", "dinesh lal yadav", "dinesh lal", "निरहुआ", "दिनेश लाल यादव"],
    "Ritesh Pandey": ["ritesh pande", "रितेश पांडे"],
    "Samar Singh": ["समर सिंह"],
    "Tuntun Yadav": ["tun tun yadav", "tuntun", "tuntunyadav", "टुनटुन यादव", "टुन टुन यादव"],
    "Shilpi Raj": ["shilpa raj", "shilpi", "shilpiraj", "shilpa", "शिल्पी राज", "शिल्पा राज"],
    "Neelkamal Singh": ["neelkamal", "nilkamal singh", "नीलकमल सिंह"],
    "Pramod Premi Yadav": ["pramod premi", "प्रमोद प्रेमी यादव"],
    "Gunjan Singh": ["गुंजन सिंह"],
    "Antra Singh Priyanka": ["antra singh", "antra priyanka", "अंतरा सिंह प्रियंका"],
    "Kalpana Patowary": ["kalpana", "कल्पना"],
    "Pradeep Pandey Chintu": ["chintu", "pradeep pandey"],
    "Ankush Raja": ["अंकुश राजा"],
    "Arijit Singh": ["arijit", "arijeet singh", "arjit singh", "अरिजीत सिंह", "अरिजीत"],
    "Shreya Ghoshal": ["shreya", "shreya ghosal", "श्रेया घोषाल"],
    "Atif Aslam": ["atif", "आतिफ असलम"],
    "Sonu Nigam": ["sonu", "सोनू निगम"],
    "Neha Kakkar": ["neha kakar", "नेहा कक्कड़"],
    "Yo Yo Honey Singh": ["honey singh", "yoyo honey singh", "yo yo honey sing", "honey sing", "हनी सिंह"],
    "Badshah": ["बादशाह"],
    "Raftaar": ["रफ्तार"],
    "Jubin Nautiyal": ["jubin", "जुबिन नौटियाल"],
    "Armaan Malik": ["arman malik", "armaan", "अरमान मलिक"],
    "Darshan Raval": ["darshan", "दर्शन रावल"],
    "B Praak": ["bpraak", "b prak", "बी प्राक"],
    "Kumar Sanu": ["कुमार सानू"],
    "Udit Narayan": ["udit", "उदित नारायण"],
    "Lata Mangeshkar": ["lata", "लता मंगेशकर"],
    "Asha Bhosle": ["asha", "आशा भोसले"],
    "Mohammed Rafi": ["rafi", "mohd rafi", "mohammad rafi", "md rafi", "मोहम्मद रफी"],
    "Kishore Kumar": ["kishore", "किशोर कुमार"],
    "A R Rahman": ["ar rahman", "a r rehman", "ar rehman", "rahman", "एआर रहमान"],
    "Sidhu Moose Wala": ["sidhu moosewala", "moosewala", "moose wala", "sidhu", "सिद्धू मूसेवाला"],
    "Diljit Dosanjh": ["diljit", "diljeet dosanjh", "दिलजीत दोसांझ"],
    "AP Dhillon": ["a p dhillon", "ap dhilon"],
    "Karan Aujla": ["karan aujla", "करण औजला"],
    "Guru Randhawa": ["गुरु रंधावा"],
    "Sapna Choudhary": ["sapna chaudhary", "sapna chowdhary", "sapna chaudhry", "सपना चौधरी"],
    "Renuka Panwar": ["renuka pawar"],
    "Taylor Swift": ["taylor", "taylor swifts"],
    "Ed Sheeran": ["ed sheran"],
    "The Weeknd": ["weeknd", "the weekend"],
    "Billie Eilish": ["billie"],
    "Justin Bieber": ["bieber"],
    "Michael Jackson": ["mj", "michael jackson"],
    "Blackpink": ["black pink"],
    "BTS": ["bangtan", "bangtan boys", "बीटीएस"],
    "Alan Walker": ["alan walker"],
    "Jungkook": ["jeon jungkook"],
    "Kim Taehyung": ["taehyung", "v taehyung"],
    "Nusrat Fateh Ali Khan": ["nusrat", "nfak"],
    "Rahat Fateh Ali Khan": ["rahat", "rfak"],
    "Ilaiyaraaja": ["ilayaraja", "ilaiyaraja", "ilayaraaja", "isaignani ilaiyaraaja"],
    "Anirudh Ravichander": ["anirudh", "anirudh ravichandar"],
    "S P Balasubrahmanyam": ["spb", "sp balasubrahmanyam", "s p balu", "sp balu"],
    "Devi Sri Prasad": ["dsp", "devisri prasad"],
    "Sid Sriram": ["sid sri ram"],
    "Hariharan": ["hari haran"],
    "Jagjit Singh": ["jagjit"],
    "Narendra Chanchal": ["narendra chanchal"],
    "Anuradha Paudwal": ["anuradha paudwal"],
    "KK": ["krishnakumar kunnath"],
    "T Series": ["tseries", "t-series", "टी सीरीज"],
    "Zee Music Company": ["zee music"],
    "Sony Music India": ["sony music"],
}

# Ye shabd ambiguous hain: kisi ke pehle naam bhi hain aur gaane ka type bhi.
# Akele search karne par -> topic (jaise Aarti = devotional).
# Poora artist naam ("Aarti Tabiyar") DB mein ho to -> artist.
# Is liye "Aarti" search par artist ka naam wala result nahi aata.
AMBIGUOUS_FIRST_NAMES = {"aarti", "arti", "bhajan", "geet", "ghazal", "lori", "naat", "mantra"}

# Extra artist namesakes (topic word se shuru hone wale naam) jo topic mein nahi aane chahiye
NAMESAKE_ARTISTS = [
    "Aarti Tabiyar", "Aarti Mukherji", "Aarti Kumar", "Aarti Bhatia", "Aarti Sharma",
    "Arti Singh", "Aarti Chaturvedi", "Aarti Sangeeta", "Aarti Raj",
]

# Search / play ke bekaar shabd (artist ya topic nahi)
PLAY_WORDS = {
    "play", "bajao", "baja", "chalao", "chala", "laga", "lagao", "lagado", "do", "de",
    "dena", "please", "pls", "plz", "mp3", "hd", "ka", "ke", "ki", "ko", "se", "ye",
    "wala", "wale", "wali", "ek", "aur", "and", "the", "of", "by", "from", "for", "me",
    "mere", "meri", "mujhe", "hai", "hain", "hi", "sunao", "sunaao", "suna", "bhai",
    "bro", "yaar", "kro", "karo", "kar", "krdo", "full", "official", "video", "videos", "audio", "lyrics", "lyrical",
    "status", "feat", "ft", "prod", "vevo",
}

# Song/gaana jaisa generic shabd (iske hone se kuch pata nahi chalta)
GENERIC_WORDS = {
    "song", "songs", "gana", "gane", "gaana", "gaane", "geet", "music", "track", "tracks",
    "new", "latest", "hit", "hits", "top", "best", "superhit", "super", "hot", "playlist",
    "all", "collection", "album", "special", "famous", "popular", "viral", "trending",
}

# ------------------------------------------------------------ TOPICS
# words        : query mein ye shabd/phrase ho to ye topic
# require_any  : (optional) title/channel mein inme se koi ek ho, tab gaana lo
# search_suffix: (optional) sirf topic ka naam likha ho to search mein ye jodo
TOPICS = {
    "devotional": {
        "words": [
            "aarti", "arti", "आरती", "bhajan", "bhajans", "भजन", "bhakti", "भक्ति",
            "devotional", "chalisa", "चालीसा", "mantra", "मंत्र", "stuti", "kirtan", "jaap",
            "jagran", "satsang", "shabad", "gurbani", "ganesh", "ganpati", "hanuman",
            "krishna", "kanha", "shiv", "shiva", "bholenath", "mahadev", "durga", "mata",
            "mata rani", "jai mata di", "sai baba", "ram", "shri ram", "jai shri ram",
            "ram naam", "radha", "vishnu", "lakshmi", "saraswati", "khatu shyam",
            "shyam baba", "balaji", "ayyappa", "murugan", "venkateswara", "waheguru",
            "naat", "hamd", "dua", "sufi kalam",
        ],
        "require_any": [
            "aarti", "arti", "आरती", "bhajan", "भजन", "bhakti", "भक्ति", "devotional",
            "chalisa", "चालीसा", "mantra", "मंत्र", "stuti", "kirtan", "jaap", "jagran",
            "shabad", "gurbani", "ganesh", "ganpati", "hanuman", "krishna", "kanha", "shiv",
            "bholenath", "mahadev", "durga", "mata", "sai baba", "shri", "jai", "radha",
            "vishnu", "lakshmi", "saraswati", "shyam", "balaji", "ayyappa", "murugan",
            "venkateswara", "waheguru", "ram", "sitaram", "om", "naat", "hamd",
        ],
        "search_suffix": " bhajan devotional songs",
    },
    "sad": {
        "words": [
            "sad", "dard", "dard bhare", "dukhi", "dukh", "gham", "ghamgeen", "bewafa",
            "bewafai", "breakup", "judai", "heartbreak", "heart broken", "emotional",
            "cry", "toota dil", "tanha", "alone", "pain", "tears", "rona", "aansu",
            "sad boy", "sad girl", "बेवफा", "दर्द", "दुख", "उदास",
        ],
    },
    "romantic": {
        "words": [
            "love", "romantic", "romance", "pyar", "pyaar", "ishq", "mohabbat", "prem",
            "couple", "valentine", "crush", "dil", "प्यार", "इश्क", "मोहब्बत",
        ],
    },
    "party": {
        "words": [
            "party", "dance", "dancing", "club", "dj", "dj remix", "remix", "edm",
            "nonstop", "non stop", "dance floor", "disco", "bass", "bass boosted",
            "mashup", "garba", "dandiya", "bhangra", "item song", "item songs",
            "बारात", "पार्टी",
        ],
    },
    "chill": {
        "words": [
            "lofi", "lo fi", "lo-fi", "chill", "chillout", "relax", "relaxing", "sleep",
            "study", "calm", "slowed", "reverb", "slowed reverb", "night drive",
            "peaceful", "meditation", "ambient", "instrumental", "piano", "acoustic",
            "unplugged", "cover",
        ],
    },
    "workout": {
        "words": [
            "gym", "workout", "motivation", "motivational", "pump up", "running",
            "fitness", "energy", "attitude", "swag",
        ],
    },
    "festive": {
        "words": [
            "shaadi", "wedding", "sangeet", "haldi", "mehndi", "bidaai", "vidaai", "holi",
            "diwali", "dipawali", "chhath", "chhat", "navratri", "ganpati bappa",
            "durga puja", "eid", "christmas", "lohri", "baisakhi", "karwa chauth",
            "teej", "rakhi", "rakshabandhan", "janmashtami", "ram navami", "dussehra",
            "independence day", "republic day", "desh bhakti", "deshbhakti", "patriotic",
            "birthday", "anniversary", "bhai dooj", "pongal", "onam", "ugadi",
            "baby shower", "godh bharai", "mundan", "tilak",
        ],
    },
    "retro": {
        "words": [
            "old", "retro", "classic", "classics", "purane", "purana", "golden era",
            "evergreen", "oldies", "vintage", "50s", "60s", "70s", "80s", "90s", "2000s",
            "2010s", "2020s", "nineties", "eighties", "seventies",
        ],
    },
    "rap": {
        "words": [
            "rap", "hiphop", "hip hop", "drill", "trap", "freestyle", "cypher", "gully rap",
            "desi hip hop", "boom bap",
        ],
    },
    "genre": {
        "words": [
            "rock", "pop", "indie", "classical", "ghazal", "qawwali", "sufi", "folk",
            "lok geet", "lokgeet", "jazz", "blues", "country", "reggae", "metal",
            "punk", "r&b", "rnb", "soul", "funk", "techno", "house", "trance", "k pop",
            "kpop", "j pop", "jpop", "anime", "bollywood", "tollywood", "kollywood",
            "mollywood", "sandalwood", "movie songs", "film songs", "filmy", "ost",
            "bgm", "background music", "theme song", "title song", "serial songs",
            "tv serial",
        ],
    },
    "kids": {
        "words": [
            "kids", "kid", "nursery", "nursery rhymes", "rhymes", "bachchon", "bachcho",
            "lullaby", "lori", "baby songs", "cartoon", "balgeet",
        ],
    },
    "mood_time": {
        "words": [
            "travel", "road trip", "roadtrip", "rain", "barish", "baarish", "monsoon",
            "night", "morning", "good morning", "evening", "summer", "winter", "sunset",
            "driving", "long drive", "bike ride",
        ],
    },
    "gender": {
        "words": [
            "girl", "girls", "ladki", "ladkiyon", "ladies", "female", "women", "woman",
            "boy", "boys", "ladka", "male", "men", "female voice", "male voice",
            "singer", "singers",
        ],
    },
    "language": {
        "words": [
            "hindi", "english", "punjabi", "bhojpuri", "haryanvi", "rajasthani", "gujarati",
            "marathi", "bengali", "bangla", "odia", "oriya", "assamese", "tamil", "telugu",
            "malayalam", "kannada", "urdu", "pahadi", "garhwali", "kumaoni", "nepali",
            "maithili", "marwadi", "korean", "japanese", "arabic", "spanish", "french",
            "turkish", "russian", "chinese", "thai", "portuguese", "german", "italian",
            "indonesian", "hinglish", "desi", "international", "foreign",
            "हिंदी", "भोजपुरी", "पंजाबी",
        ],
    },
    "charts": {
        "words": [
            "top 10", "top 20", "top 50", "top 100", "billboard", "charts", "chartbuster",
            "jukebox", "weekly", "monthly", "this year", "2023", "2024", "2025", "2026",
        ],
    },
}
